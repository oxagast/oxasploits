/*
 * atril_pdf_harness.c
 *
 * Exercise every EvDocument API surface that the PDF (poppler) backend
 * implements, in the same order Atril's UI/daemon/thumbnailer would touch
 * them after a user opens an untrusted PDF.
 *
 * Usage:
 *   atril_pdf_harness <file.pdf> [--all-pages] [--quiet] [--max-pages N]
 *                                [--no-selection]
 *
 * Exit codes:
 *   0  document loaded and every surface was exercised (backend errors are OK)
 *   1  document could not be loaded at all
 *   2  bad usage
 *
 * The harness deliberately tolerates backend errors: a malformed PDF is
 * *supposed* to fail to load. What we care about is memory-safety violations;
 * those are reported by ASan/UBSan and abort the process.
 */

#include <config.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <glib.h>
#include <glib/gstdio.h>
#include <gtk/gtk.h>
#include <gdk-pixbuf/gdk-pixbuf.h>
#include <cairo.h>

#include "ev-document.h"
#include "ev-init.h"
#include "ev-file-helpers.h"
#include "ev-document-factory.h"
#include "ev-document-annotations.h"
#include "ev-document-attachments.h"
#include "ev-document-find.h"
#include "ev-document-fonts.h"
#include "ev-document-forms.h"
#include "ev-document-images.h"
#include "ev-document-layers.h"
#include "ev-document-links.h"
#include "ev-document-misc.h"
#include "ev-document-print.h"
#include "ev-document-security.h"
#include "ev-document-text.h"
#include "ev-document-thumbnails.h"
#include "ev-document-transition.h"
#include "ev-file-exporter.h"
#include "ev-selection.h"

static gboolean opt_all_pages = FALSE;
static gboolean opt_quiet = FALSE;
static gint     opt_max_pages = 8;
/* The selection-render path reports a UBSan null-memset on essentially every
 * page (the known V4 finding). It masks every other bug in a run, so allow it
 * to be skipped. */
static gboolean opt_no_selection = FALSE;

#define LOG(...) do { if (!opt_quiet) g_printerr (__VA_ARGS__); } while (0)

static gint
page_count_to_walk (gint n_pages)
{
	if (opt_all_pages)
		return n_pages;
	return MIN (n_pages, opt_max_pages);
}

/* ------------------------------------------------------------------ */
/* EvDocument                                                          */
/* ------------------------------------------------------------------ */

static void
walk_document_info (EvDocument *document)
{
	EvDocumentInfo *info = ev_document_get_info (document);

	if (!info)
		return;

	LOG ("  info: title=%s format=%s author=%s subject=%s keywords=%s\n",
	     info->title ? info->title : "(null)",
	     info->format ? info->format : "(null)",
	     info->author ? info->author : "(null)",
	     info->subject ? info->subject : "(null)",
	     info->keywords ? info->keywords : "(null)");
	LOG ("  info: creator=%s producer=%s n_pages=%d linearized=%s\n",
	     info->creator ? info->creator : "(null)",
	     info->producer ? info->producer : "(null)",
	     info->n_pages,
	     info->linearized ? "yes" : "no");
	LOG ("  info: layout=%d mode=%d permissions=0x%x\n",
	     info->layout, info->mode, info->permissions);
	LOG ("  info: paper=%.2fx%.2f mm security=%d\n",
	     info->paper_width, info->paper_height, info->security);

	if (info->license) {
		LOG ("  license: text=%s uri=%s web=%s\n",
		     ev_document_license_get_text (info->license) ?
		     ev_document_license_get_text (info->license) : "(null)",
		     ev_document_license_get_uri (info->license) ?
		     ev_document_license_get_uri (info->license) : "(null)",
		     ev_document_license_get_web_statement (info->license) ?
		     ev_document_license_get_web_statement (info->license) : "(null)");
	}

	/* ev_document_get_info() returns a borrowed reference. */
}

static void
walk_page (EvDocument *document, gint index, gint n_pages)
{
	EvPage *page;
	gdouble width = 0, height = 0;
	gchar  *label;
	EvRenderContext *rc;

	page = ev_document_get_page (document, index);
	if (!page)
		return;

	ev_document_get_page_size (document, index, &width, &height);
	LOG ("  page %d: %.2fx%.2f pt\n", index, width, height);

	label = ev_document_get_page_label (document, index);
	if (label)
		LOG ("    label: %s\n", label);

	/* Render at a couple of scales/rotations, like the view + thumbnails. */
	rc = ev_render_context_new (page, 0, 1.0);
	if (EV_IS_DOCUMENT (document)) {
		cairo_surface_t *surface;

		surface = ev_document_render (document, rc);
		if (surface) {
			LOG ("    render 100%%: %dx%d\n",
			     cairo_image_surface_get_width (surface),
			     cairo_image_surface_get_height (surface));
			/* Consumers in libview copy via gdk-pixbuf */
			GdkPixbuf *pixbuf = ev_document_misc_pixbuf_from_surface (surface);
			if (pixbuf)
				g_object_unref (pixbuf);
			cairo_surface_destroy (surface);
		}
	}

	ev_render_context_set_scale (rc, 0.25);
	ev_render_context_set_rotation (rc, 90);
	{
		cairo_surface_t *surface = ev_document_render (document, rc);
		if (surface)
			cairo_surface_destroy (surface);
	}
	ev_render_context_set_scale (rc, 2.0);
	ev_render_context_set_rotation (rc, 270);
	{
		cairo_surface_t *surface = ev_document_render (document, rc);
		if (surface)
			cairo_surface_destroy (surface);
	}

	g_object_unref (rc);

	/* Thumbnails, with and without border: the sidebar path. */
	if (EV_IS_DOCUMENT_THUMBNAILS (document)) {
		gint tw = 0, th = 0;

		rc = ev_render_context_new (page, 0, 0.2);
		ev_document_thumbnails_get_dimensions (EV_DOCUMENT_THUMBNAILS (document),
						       rc, &tw, &th);
		LOG ("    thumb dims: %dx%d\n", tw, th);

		{
			GdkPixbuf *pixbuf;

			pixbuf = ev_document_thumbnails_get_thumbnail (
				EV_DOCUMENT_THUMBNAILS (document), rc, TRUE);
			if (pixbuf)
				g_object_unref (pixbuf);
			pixbuf = ev_document_thumbnails_get_thumbnail (
				EV_DOCUMENT_THUMBNAILS (document), rc, FALSE);
			if (pixbuf)
				g_object_unref (pixbuf);
		}
		g_object_unref (rc);
	}

	/* Text extraction + text mapping: selection, a11y, find. */
	if (EV_IS_DOCUMENT_TEXT (document)) {
		gchar *text;

		text = ev_document_text_get_text (EV_DOCUMENT_TEXT (document), page);
		if (text) {
			LOG ("    text: %" G_GSIZE_FORMAT " bytes\n", strlen (text));
			g_free (text);
		}

		{
			EvRectangle *areas = NULL;
			guint n_areas = 0;

			if (ev_document_text_get_text_layout (EV_DOCUMENT_TEXT (document),
							      page, &areas, &n_areas)) {
				LOG ("    layout: %u areas\n", n_areas);
				g_free (areas);
			}
		}

		{
			cairo_region_t *region;

			region = ev_document_text_get_text_mapping (EV_DOCUMENT_TEXT (document),
								    page);
			if (region)
				cairo_region_destroy (region);
		}

		{
			PangoAttrList *attrs;

			attrs = ev_document_text_get_text_attrs (EV_DOCUMENT_TEXT (document),
								 page);
			if (attrs)
				pango_attr_list_unref (attrs);
		}
	}

	/* Links: tooltip + link mapping + external action dispatch. */
	if (EV_IS_DOCUMENT_LINKS (document)) {
		EvMappingList *links;

		links = ev_document_links_get_links (EV_DOCUMENT_LINKS (document), page);
		if (links) {
			GList *l;
			guint n = ev_mapping_list_length (links);

			LOG ("    links: %u\n", n);
			for (l = ev_mapping_list_get_list (links); l; l = l->next) {
				EvMapping *mapping = (EvMapping *)l->data;
				EvLink *link = EV_LINK (mapping->data);
				EvLinkAction *action;
				const gchar *title = ev_link_get_title (link);

				if (title)
					LOG ("      link title: '%s'\n", title);

				action = ev_link_get_action (link);
				if (action) {
					LOG ("      action type: %d uri=%s file=%s name=%s\n",
					     ev_link_action_get_action_type (action),
					     ev_link_action_get_uri (action) ?
					     ev_link_action_get_uri (action) : "(null)",
					     ev_link_action_get_filename (action) ?
					     ev_link_action_get_filename (action) : "(null)",
					     ev_link_action_get_name (action) ?
					     ev_link_action_get_name (action) : "(null)");

					/* Resolve GoTo destinations, like view does. */
					if (ev_link_action_get_action_type (action) ==
					    EV_LINK_ACTION_TYPE_GOTO_DEST) {
						EvLinkDest *dest = ev_link_action_get_dest (action);

						if (dest) {
							LOG ("      dest page: %d type: %d\n",
							     ev_link_dest_get_page (dest),
							     ev_link_dest_get_dest_type (dest));
							/* Named destinations are re-resolved
							 * through the document. */
							if (ev_link_dest_get_dest_type (dest) ==
							    EV_LINK_DEST_TYPE_NAMED) {
								EvLinkDest *d2;
								const gchar *named =
									ev_link_dest_get_named_dest (dest);

								d2 = ev_document_links_find_link_dest (
									EV_DOCUMENT_LINKS (document),
									named);
								if (d2) {
									LOG ("      named dest -> page %d\n",
									     ev_link_dest_get_page (d2));
									g_object_unref (d2);
								}
							}
						}
					}
				}
			}
			ev_mapping_list_unref (links);
		}

		{
			EvLinkDest *page_dest = ev_link_dest_new_page (index);
			gchar *page_label = ev_document_links_get_dest_page_label (
				EV_DOCUMENT_LINKS (document), page_dest);

			g_free (page_label);
			g_object_unref (page_dest);
		}
	}

	/* Annotations: sidebar, tooltips, popup windows. */
	if (EV_IS_DOCUMENT_ANNOTATIONS (document)) {
		EvMappingList *annots;

		annots = ev_document_annotations_get_annotations (
			EV_DOCUMENT_ANNOTATIONS (document), page);
		if (annots) {
			GList *l;

			LOG ("    annotations: %u\n",
			     ev_mapping_list_length (annots));
			for (l = ev_mapping_list_get_list (annots); l; l = l->next) {
				EvMapping *mapping = (EvMapping *)l->data;
				EvAnnotation *annot = EV_ANNOTATION (mapping->data);
				const gchar *contents = ev_annotation_get_contents (annot);
				const gchar *name = ev_annotation_get_name (annot);
				const gchar *modified = ev_annotation_get_modified (annot);

				LOG ("      annot type=%d name=%s contents=%s modified=%s\n",
				     ev_annotation_get_annotation_type (annot),
				     name ? name : "(null)",
				     contents ? contents : "(null)",
				     modified ? modified : "(null)");

				if (EV_IS_ANNOTATION_MARKUP (annot)) {
					const gchar *label =
						ev_annotation_markup_get_label (
							EV_ANNOTATION_MARKUP (annot));
					EvRectangle rect;
					GdkRGBA rgba;

					LOG ("      label=%s opacity=%.3f popup=%d\n",
					     label ? label : "(null)",
					     ev_annotation_markup_get_opacity (
						     EV_ANNOTATION_MARKUP (annot)),
					     ev_annotation_markup_has_popup (
						     EV_ANNOTATION_MARKUP (annot)));
					ev_annotation_markup_get_rectangle (
						EV_ANNOTATION_MARKUP (annot), &rect);
					ev_annotation_get_rgba (annot, &rgba);
				}

				if (EV_IS_ANNOTATION_ATTACHMENT (annot)) {
					EvAttachment *att =
						ev_annotation_attachment_get_attachment (
							EV_ANNOTATION_ATTACHMENT (annot));
					if (att) {
						LOG ("      annot attachment: %s (%s)\n",
						     ev_attachment_get_name (att),
						     ev_attachment_get_mime_type (att));
						/* Exercise the save path that the UI
						 * uses for "open attachment". */
						{
							GFile *tmp = g_file_new_tmp ("atril-fuzz-XXXXXX", NULL, NULL);
							if (tmp) {
								ev_attachment_save (att, tmp, NULL);
								g_object_unref (tmp);
							}
						}
					}
				}
			}
			ev_mapping_list_unref (annots);
		}
	}

	/* Form fields: AcroForm widgets. */
	if (EV_IS_DOCUMENT_FORMS (document)) {
		EvMappingList *fields;

		fields = ev_document_forms_get_form_fields (EV_DOCUMENT_FORMS (document),
							   page);
		if (fields) {
			GList *l;

			LOG ("    form fields: %u\n",
			     ev_mapping_list_length (fields));
			for (l = ev_mapping_list_get_list (fields); l; l = l->next) {
				EvMapping *mapping = (EvMapping *)l->data;
				EvFormField *field = EV_FORM_FIELD (mapping->data);

				LOG ("      field id=%d type=%s readonly=%d font_size=%.2f\n",
				     field->id, G_OBJECT_TYPE_NAME (field),
				     field->is_read_only, field->font_size);

				if (EV_IS_FORM_FIELD_TEXT (field)) {
					gchar *text =
						ev_document_forms_form_field_text_get_text (
							EV_DOCUMENT_FORMS (document), field);
					g_free (text);
				} else if (EV_IS_FORM_FIELD_CHOICE (field)) {
					gint n_items, i2;
					gchar *item;

					n_items = ev_document_forms_form_field_choice_get_n_items (
						EV_DOCUMENT_FORMS (document), field);
					for (i2 = 0; i2 < n_items; i2++) {
						item = ev_document_forms_form_field_choice_get_item (
							EV_DOCUMENT_FORMS (document),
							field, i2);
						g_free (item);
						ev_document_forms_form_field_choice_is_item_selected (
							EV_DOCUMENT_FORMS (document),
							field, i2);
					}
				} else if (EV_IS_FORM_FIELD_BUTTON (field)) {
					ev_document_forms_form_field_button_get_state (
						EV_DOCUMENT_FORMS (document), field);
				}
			}
			ev_mapping_list_unref (fields);
		}
	}

	/* Images on the page (image extraction / copy). */
	if (EV_IS_DOCUMENT_IMAGES (document)) {
		EvMappingList *images;

		images = ev_document_images_get_image_mapping (
			EV_DOCUMENT_IMAGES (document), page);
		if (images) {
			GList *l;

			LOG ("    images: %u\n", ev_mapping_list_length (images));
			for (l = ev_mapping_list_get_list (images); l; l = l->next) {
				EvMapping *mapping = (EvMapping *)l->data;
				GdkPixbuf *pixbuf;

				pixbuf = ev_document_images_get_image (
					EV_DOCUMENT_IMAGES (document),
					EV_IMAGE (mapping->data));
				if (pixbuf)
					g_object_unref (pixbuf);
			}
			ev_mapping_list_unref (images);
		}
	}

	/* Selection rendering + selected text (mouse drag). */
	if (EV_IS_SELECTION (document) && !opt_no_selection) {
		gint w = MAX ((gint) (width + 0.5), 1);
		gint h = MAX ((gint) (height + 0.5), 1);
		EvRectangle points = { 0, 0, w / 2, h / 2 };
		EvRectangle old_points = { 0, 0, 0, 0 };
		GdkColor text = { 0, 0, 0, 0 };
		GdkColor base = { 0, 0, 0, 0 };
		cairo_surface_t *surface = NULL;
		gchar *selected;
		cairo_region_t *region;

		rc = ev_render_context_new (page, 0, 1.0);
		ev_selection_render_selection (EV_SELECTION (document), rc,
					       &surface, &points, &old_points,
					       EV_SELECTION_STYLE_GLYPH,
					       &text, &base);
		if (surface)
			cairo_surface_destroy (surface);

		selected = ev_selection_get_selected_text (EV_SELECTION (document),
							   page,
							   EV_SELECTION_STYLE_WORD,
							   &points);
		g_free (selected);

		region = ev_selection_get_selection_region (EV_SELECTION (document), rc,
							    EV_SELECTION_STYLE_LINE,
							    &points);
		if (region)
			cairo_region_destroy (region);
		g_object_unref (rc);
	}

	/* Transition effects (presentation mode). */
	if (EV_IS_DOCUMENT_TRANSITION (document)) {
		gdouble duration;
		EvTransitionEffect *effect;

		duration = ev_document_transition_get_page_duration (
			EV_DOCUMENT_TRANSITION (document), index);
		effect = ev_document_transition_get_effect (
			EV_DOCUMENT_TRANSITION (document), index);
		LOG ("    transition: duration=%.3f effect=%p\n", duration, (void *) effect);
		if (effect)
			g_object_unref (effect);
	}

	/* Printing: render_for_printing into a scratch surface. */
	if (EV_IS_DOCUMENT_PRINT (document)) {
		gint w = MAX ((gint) (width + 0.5), 1);
		gint h = MAX ((gint) (height + 0.5), 1);
		cairo_surface_t *surface;
		cairo_t *cr;

		surface = cairo_image_surface_create (CAIRO_FORMAT_ARGB32, w, h);
		cr = cairo_create (surface);
		ev_document_print_print_page (EV_DOCUMENT_PRINT (document), page, cr);
		cairo_destroy (cr);
		cairo_surface_destroy (surface);
	}

	/* Page labels are cached by EvDocument; look up by label. */
	if (label) {
		gint found = -1;

		if (ev_document_find_page_by_label (document, label, &found))
			LOG ("    find_page_by_label(%s) = %d\n", label, found);
		g_free (label);
	}

	g_object_unref (page);
}

/* ------------------------------------------------------------------ */
/* Document-level surfaces                                             */
/* ------------------------------------------------------------------ */

static void
walk_document_links_model (EvDocument *document)
{
	GtkTreeModel *model;

	if (!EV_IS_DOCUMENT_LINKS (document))
		return;

	if (!ev_document_links_has_document_links (EV_DOCUMENT_LINKS (document)))
		return;

	model = ev_document_links_get_links_model (EV_DOCUMENT_LINKS (document));
	if (model) {
		LOG ("  links model: %d rows\n", gtk_tree_model_iter_n_children (model, NULL));
		g_object_unref (model);
	}

	/* Named destination lookups with attacker-controlled names. */
	{
		EvLinkDest *dest;

		dest = ev_document_links_find_link_dest (EV_DOCUMENT_LINKS (document), "foo");
		if (dest)
			g_object_unref (dest);

		/* Exercise named-destination page lookup, which the outline
		 * and a11y code use. */
		ev_document_links_find_link_page (EV_DOCUMENT_LINKS (document),
						  "foo");
	}
}

static void
walk_document_attachments (EvDocument *document)
{
	GList *attachments, *l;

	if (!EV_IS_DOCUMENT_ATTACHMENTS (document))
		return;

	if (!ev_document_attachments_has_attachments (
		    EV_DOCUMENT_ATTACHMENTS (document)))
		return;

	attachments = ev_document_attachments_get_attachments (
		EV_DOCUMENT_ATTACHMENTS (document));
	for (l = attachments; l; l = l->next) {
		EvAttachment *att = EV_ATTACHMENT (l->data);

		LOG ("  attachment: name='%s' desc='%s' mime=%s\n",
		     ev_attachment_get_name (att),
		     ev_attachment_get_description (att) ?
		     ev_attachment_get_description (att) : "(null)",
		     ev_attachment_get_mime_type (att));

		/* The drag-out and "open attachment" paths both create a
		 * temp name from the attachment name. */
		{
			gchar *template;
			GFile *file;

			template = g_strdup_printf ("%s.XXXXXX",
						    ev_attachment_get_name (att));
			file = ev_mkstemp_file (template, NULL);
			g_free (template);
			if (file) {
				ev_attachment_save (att, file, NULL);
				g_object_unref (file);
			}
		}
		g_object_unref (att);
	}
	g_list_free (attachments);
}

static void
walk_document_fonts (EvDocument *document, gint n_pages)
{
	GtkListStore *model;

	if (!EV_IS_DOCUMENT_FONTS (document))
		return;

	if (!ev_document_fonts_scan (EV_DOCUMENT_FONTS (document),
				     MIN (n_pages, 8)))
		return;

	model = gtk_list_store_new (3, G_TYPE_STRING, G_TYPE_STRING, G_TYPE_STRING);
	ev_document_fonts_fill_model (EV_DOCUMENT_FONTS (document),
				      GTK_TREE_MODEL (model));
	LOG ("  fonts: %d entries\n", gtk_tree_model_iter_n_children (GTK_TREE_MODEL (model), NULL));
	g_object_unref (model);
}

static void
walk_document_layers (EvDocument *document)
{
	GtkTreeModel *model;

	if (!EV_IS_DOCUMENT_LAYERS (document))
		return;

	if (!ev_document_layers_has_layers (EV_DOCUMENT_LAYERS (document)))
		return;

	model = ev_document_layers_get_layers (EV_DOCUMENT_LAYERS (document));
	if (model) {
		LOG ("  layers: %d rows\n",
		     gtk_tree_model_iter_n_children (model, NULL));
		g_object_unref (model);
	}
}

static void
walk_document_security (EvDocument *document, GError *load_error)
{
	if (!EV_IS_DOCUMENT_SECURITY (document))
		return;

	LOG ("  security: has_security=%d\n",
	     ev_document_security_has_document_security (
		     EV_DOCUMENT_SECURITY (document)));

	if (load_error &&
	    g_error_matches (load_error, EV_DOCUMENT_ERROR,
			     EV_DOCUMENT_ERROR_ENCRYPTED)) {
		/* Same retry the password prompt performs. */
		ev_document_security_set_password (
			EV_DOCUMENT_SECURITY (document), "owner");
	}
}

static void
walk_document_find (EvDocument *document, gint n_pages)
{
	static const gchar *needles[] = {
		"a", "A", "the", "Page", "\xc3\xa9", "%s", "%n", "..",
		"\\\\", "\"", "'", NULL
	};
	gint i;

	if (!EV_IS_DOCUMENT_FIND (document))
		return;

	for (i = 0; needles[i] != NULL; i++) {
		gint p;

		for (p = 0; p < MIN (n_pages, 3); p++) {
			EvPage *page;
			GList *hits, *l;

			page = ev_document_get_page (document, p);
			if (!page)
				continue;

			hits = ev_document_find_find_text (EV_DOCUMENT_FIND (document),
							   page, needles[i], FALSE);
			for (l = hits; l; l = l->next)
				ev_rectangle_free ((EvRectangle *)l->data);
			g_list_free (hits);

			/* check_for_hits() is only implemented by the web
			 * backend; calling it on a non-web document would
			 * dereference a NULL vfunc. Guard like ev-jobs.c does. */
			if (document->iswebdocument) {
				ev_document_find_check_for_hits (
					EV_DOCUMENT_FIND (document),
					page, needles[i], TRUE);
			}

			g_object_unref (page);
		}
	}
}

static void
walk_document_export (EvDocument *document, gint n_pages, const gchar *outdir)
{
	EvFileExporterCapabilities caps;
	EvFileExporterContext fc;
	gchar *out = NULL;
	EvFileExporterFormat formats[] = { EV_FILE_FORMAT_PS, EV_FILE_FORMAT_PDF };
	gint i;

	if (!EV_IS_FILE_EXPORTER (document))
		return;

	/* Mirror the UI: exporting/printing needs at least one page. */
	if (n_pages <= 0)
		return;

	caps = ev_file_exporter_get_capabilities (EV_FILE_EXPORTER (document));
	LOG ("  exporter caps: 0x%x\n", caps);

	for (i = 0; i < (gint) G_N_ELEMENTS (formats); i++) {
		gint p;

		out = g_build_filename (outdir, "export-XXXXXX", NULL);
		{
			gint fd = g_mkstemp (out);
			if (fd >= 0)
				close (fd);
		}

		memset (&fc, 0, sizeof (fc));
		fc.format = formats[i];
		fc.filename = out;
		fc.first_page = 0;
		fc.last_page = MIN (n_pages, 3) - 1;
		if (fc.last_page < fc.first_page)
			fc.last_page = fc.first_page;
		fc.paper_width = 612;
		fc.paper_height = 792;
		fc.pages_per_sheet = 1;

		ev_file_exporter_begin (EV_FILE_EXPORTER (document), &fc);
		for (p = 0; p < MIN (n_pages, 3); p++) {
			EvPage *page = ev_document_get_page (document, p);
			EvRenderContext *rc;

			if (!page)
				continue;

			rc = ev_render_context_new (page, 0, 1.0);
			ev_file_exporter_begin_page (EV_FILE_EXPORTER (document));
			ev_file_exporter_do_page (EV_FILE_EXPORTER (document), rc);
			ev_file_exporter_end_page (EV_FILE_EXPORTER (document));
			g_object_unref (rc);
			g_object_unref (page);
		}
		ev_file_exporter_end (EV_FILE_EXPORTER (document));

		g_unlink (out);
		g_free (out);
	}
}

/* ------------------------------------------------------------------ */

int
main (int argc, char **argv)
{
	const gchar *path = NULL;
	GFile *file;
	gchar *uri;
	EvDocument *document = NULL;
	GError *error = NULL;
	gint n_pages;
	gint i;
	gchar *outdir;

	{
		gint a;

		for (a = 1; a < argc; a++) {
			if (g_str_equal (argv[a], "--all-pages"))
				opt_all_pages = TRUE;
			else if (g_str_equal (argv[a], "--quiet"))
				opt_quiet = TRUE;
			else if (g_str_equal (argv[a], "--max-pages") && a + 1 < argc)
				opt_max_pages = atoi (argv[++a]);
			else if (g_str_equal (argv[a], "--no-selection"))
				opt_no_selection = TRUE;
			else if (argv[a][0] == '-') {
				fprintf (stderr, "unknown option %s\n", argv[a]);
				return 2;
			} else
				path = argv[a];
		}
	}

	if (!path) {
		fprintf (stderr, "usage: %s <file.pdf> [--all-pages] [--max-pages N] [--quiet]\n",
			 argv[0]);
		return 2;
	}

	/* GTK is needed for GtkTreeModel in the links/fonts/layers ifaces. */
	if (!gtk_init_check (&argc, &argv)) {
		/* Fall back to plain GLib/type system.  The backend only uses
		 * GTK data types, it does not require a display. */
		g_setenv ("GDK_BACKEND", "broadway", TRUE);
	}

	if (!ev_init ()) {
		fprintf (stderr, "ev_init() failed; no backends found (EV_BACKENDSDIR=%s)\n",
			 EV_BACKENDSDIR);
		return 1;
	}

	file = g_file_new_for_commandline_arg (path);
	uri = g_file_get_uri (file);
	g_object_unref (file);

	document = ev_document_factory_get_document (uri, &error);
	if (!document) {
		LOG ("load failed: %s\n", error ? error->message : "(no error)");
		g_clear_error (&error);
		g_free (uri);
		ev_shutdown ();
		return 1;
	}

	/* Encrypted documents are still returned with error set. */
	if (error) {
		LOG ("load warning: %s\n", error->message);
	}

	LOG ("loaded %s: %s (%d pages)\n",
	     uri, G_OBJECT_TYPE_NAME (document),
	     ev_document_get_n_pages (document));

	n_pages = ev_document_get_n_pages (document);
	if (n_pages <= 0) {
		LOG ("  no pages; still exercising document-level surfaces\n");
	}

	/* ---- document-level ---- */
	walk_document_info (document);
	walk_document_security (document, error);
	walk_document_links_model (document);
	walk_document_attachments (document);
	walk_document_fonts (document, n_pages);
	walk_document_layers (document);
	walk_document_find (document, n_pages);

	outdir = g_dir_make_tmp ("atril-fuzz-XXXXXX", NULL);
	if (outdir) {
		walk_document_export (document, n_pages, outdir);
		g_rmdir (outdir);
		g_free (outdir);
	}

	/* ---- per page ---- */
	for (i = 0; i < page_count_to_walk (n_pages); i++)
		walk_page (document, i, n_pages);

	g_clear_error (&error);
	g_object_unref (document);
	g_free (uri);
	ev_shutdown ();

	return 0;
}
