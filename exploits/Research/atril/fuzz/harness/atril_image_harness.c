/*
 * atril_image_harness.c
 *
 * Feed one file through every image-decoding path Atril reaches for
 * document-supplied data, in the same shapes the viewer and the thumbnailer
 * use them:
 *
 *   1. GdkPixbufLoader, streamed in small chunks
 *      (comics backend: gdk_pixbuf_loader_write on archive entry bytes)
 *   2. GdkPixbufLoader with a size-prepared handler requesting a thumbnail
 *      (comics: render_pixbuf_size_prepared_cb)
 *   3. GdkPixbuf "at size" / "at scale" loaders
 *      (pixbuf backend, sidebar icons, thumbnails)
 *   4. raw format sniffing, then the loader for the sniffed type
 *
 * The point is the decoders, not Atril: a crash here is in libjpeg, libtiff,
 * libwebp, libavif, libheif, libjxl, OpenEXR, librsvg, or in glib's loader
 * plumbing. Those libraries are exactly what a PDF can reach through
 * DCTDecode / JPXDecode / JBIG2 / CCITT image XObjects, so a bug found here
 * is reachable from a PDF even when the PDF syntax itself is valid.
 *
 * Usage:
 *   atril_image_harness <file> [--quiet]
 *
 * Exit codes:
 *   0  every decoder path was exercised (decode errors are expected and OK)
 *   2  bad usage
 *
 * As with the PDF harness, decode failures are normal; memory-safety reports
 * from ASan/UBSan abort the process and that is what we collect.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <glib.h>
#include <glib/gstdio.h>
#include <unistd.h>
#include <gdk-pixbuf/gdk-pixbuf.h>

static gboolean opt_quiet = FALSE;
#define LOG(...) do { if (!opt_quiet) g_printerr (__VA_ARGS__); } while (0)

#define CHUNK 512

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

static GBytes *
read_file (const gchar *path, GError **error)
{
	gchar *contents = NULL;
	gsize  length = 0;

	if (!g_file_get_contents (path, &contents, &length, error))
		return NULL;

	return g_bytes_new_take (contents, length);
}

/* Stream the whole buffer through a fresh loader in CHUNK-sized writes, the
 * way the comics backend feeds archive entry data. */
static void
try_stream_loader (GBytes *bytes, gboolean size_prepared, gint thumb_w, gint thumb_h)
{
	GdkPixbufLoader *loader;
	GdkPixbuf       *pixbuf;
	const guchar    *data;
	gsize            len, off;
	GError          *error = NULL;

	loader = gdk_pixbuf_loader_new ();

	if (size_prepared) {
		/* comics: render_pixbuf_size_prepared_cb clamps to the render size */
		gdk_pixbuf_loader_set_size (loader, thumb_w, thumb_h);
	}

	data = g_bytes_get_data (bytes, &len);
	for (off = 0; off < len; off += CHUNK) {
		gsize n = MIN ((gsize) CHUNK, len - off);

		if (!gdk_pixbuf_loader_write (loader, data + off, n, &error)) {
			LOG ("    stream write stopped at %" G_GSIZE_FORMAT ": %s\n",
			     off, error ? error->message : "?");
			g_clear_error (&error);
			break;
		}
	}

	/* Close even after a failed write: the loader may still finalise state. */
	if (!gdk_pixbuf_loader_close (loader, &error)) {
		if (error) {
			LOG ("    stream close: %s\n", error->message);
			g_clear_error (&error);
		}
	}

	pixbuf = gdk_pixbuf_loader_get_pixbuf (loader);
	if (pixbuf) {
		LOG ("    stream %s: %dx%d, %d channels, rowstride %d\n",
		     size_prepared ? "(sized)" : "(raw)",
		     gdk_pixbuf_get_width (pixbuf),
		     gdk_pixbuf_get_height (pixbuf),
		     gdk_pixbuf_get_n_channels (pixbuf),
		     gdk_pixbuf_get_rowstride (pixbuf));

		/* Touch the pixels so any lazy decode / partial buffer shows up. */
		{
			guchar *px = gdk_pixbuf_get_pixels (pixbuf);
			gint    h = gdk_pixbuf_get_height (pixbuf);
			gint    rs = gdk_pixbuf_get_rowstride (pixbuf);
			gint    n = gdk_pixbuf_get_n_channels (pixbuf);
			volatile guint acc = 0;

			for (gint y = 0; y < h; y++) {
				for (gint x = 0; x < gdk_pixbuf_get_width (pixbuf); x++)
					acc += px[(gsize) y * rs + (gsize) x * n];
			}
		}
	}

	g_object_unref (loader);
}

/* Report the decoder gdk-pixbuf picks. gdk_pixbuf_get_file_info wants a
 * path, so use the temp file the caller already wrote. */
static void
report_format (const gchar *path)
{
	GdkPixbufFormat *fmt;
	gchar           *name;
	gint             w = 0, h = 0;

	fmt = gdk_pixbuf_get_file_info (path, &w, &h);
	if (!fmt) {
		LOG ("    sniff: not recognised\n");
		return;
	}

	name = gdk_pixbuf_format_get_name (fmt);
	LOG ("    sniff: %s (%dx%d)\n", name, w, h);
	g_free (name);
}

/* ------------------------------------------------------------------ */

int
main (int argc, char **argv)
{
	GBytes  *bytes;
	GError  *error = NULL;
	gchar   *path = NULL;
	gchar   *tmp = NULL;
	GdkPixbuf *pixbuf;
	gint     fd;

	if (argc < 2) {
		g_printerr ("usage: %s <file> [--quiet]\n", argv[0]);
		return 2;
	}

	for (int i = 1; i < argc; i++) {
		if (g_strcmp0 (argv[i], "--quiet") == 0)
			opt_quiet = TRUE;
		else if (!path)
			path = argv[i];
	}

	bytes = read_file (path, &error);
	if (!bytes) {
		LOG ("cannot read %s: %s\n", path, error ? error->message : "?");
		g_clear_error (&error);
		return 0;
	}

	LOG ("%s: %" G_GSIZE_FORMAT " bytes\n", path, g_bytes_get_size (bytes));

	/* A real path is needed for the file-based loaders and for sniffing. */
	fd = g_file_open_tmp ("atril-img-XXXXXX", &tmp, &error);
	if (fd == -1) {
		LOG ("cannot create temp file: %s\n", error ? error->message : "?");
		g_clear_error (&error);
		g_bytes_unref (bytes);
		return 0;
	}
	{
		const gchar *d = g_bytes_get_data (bytes, NULL);
		gsize        n = g_bytes_get_size (bytes);
		gsize        off = 0;

		while (off < n) {
			ssize_t w = write (fd, d + off, n - off);

			if (w <= 0)
				break;
			off += (gsize) w;
		}
	}
	close (fd);

	report_format (tmp);

	/* 1. streamed, raw: the comics backend feed */
	try_stream_loader (bytes, FALSE, 0, 0);

	/* 2. streamed with a thumbnail size request (comics size-prepared path) */
	try_stream_loader (bytes, TRUE, 128, 128);
	try_stream_loader (bytes, TRUE, 1, 1);
	/* Large but bounded: a 100000x100000 request would be ~30 GiB. */
	try_stream_loader (bytes, TRUE, 4096, 4096);

	/* 3. file-at-size / file-at-scale / plain: pixbuf backend + thumbnails */
	pixbuf = gdk_pixbuf_new_from_file_at_size (tmp, 128, 128, NULL);
	if (pixbuf) {
		LOG ("    file_at_size: %dx%d\n",
		     gdk_pixbuf_get_width (pixbuf), gdk_pixbuf_get_height (pixbuf));
		g_object_unref (pixbuf);
	}

	pixbuf = gdk_pixbuf_new_from_file_at_scale (tmp, 64, 64, TRUE, NULL);
	if (pixbuf) {
		LOG ("    file_at_scale: %dx%d\n",
		     gdk_pixbuf_get_width (pixbuf), gdk_pixbuf_get_height (pixbuf));
		g_object_unref (pixbuf);
	}

	pixbuf = gdk_pixbuf_new_from_file (tmp, NULL);
	if (pixbuf) {
		LOG ("    file: %dx%d\n",
		     gdk_pixbuf_get_width (pixbuf), gdk_pixbuf_get_height (pixbuf));
		g_object_unref (pixbuf);
	}

	g_unlink (tmp);
	g_free (tmp);

	g_bytes_unref (bytes);
	return 0;
}
