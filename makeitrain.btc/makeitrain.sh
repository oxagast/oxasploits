#!/bin/bash
## ./makeitrain.sh bitcoin-qt.crashdump.core


COREFN=$1;
CLEN=98304;

echo "Attempting to recover wallet.dat from $COREFN";
echo "Using wallet length: $CLEN characters... (adjusting CLEN may help if wallet is not recovered)";

COUNT=0;
echo "Grepping for magic numbers...";
xxd $COREFN | grep "6231 0500" > walletoffsets;
while read START; do
let "COUNT++"
POFF=$(echo $START | sed -e 's/.*b1//' | head -n $COUNT | tail -n 1 | wc -c)
POFFH=$(printf "%x\n" $POFF);
OFFSET=$(echo $START | sed -e 's/:.*//');
OFFSET="0x$OFFSET";
POFFH="0x$POFFH";
echo "Offset: $OFFSET Difference: $POFFH";
HEXSUBBED=$(printf "0x%X\n" $(($OFFSET - ( $POFFH - 0x03))));
echo $HEXSUBBED;
echo "Seeking to $HEXSUBBED...";
xxd -p -l $CLEN --seek $HEXSUBBED $COREFN > test$COUNT.xxd
echo "Writing new wallet: test$COUNT.dat...";
xxd -p -r test$COUNT.xxd > test$COUNT.dat;
xxd test$COUNT.dat | head -n 1;
done < walletoffsets;
echo "Removing temporary files";
rm test*.xxd;
rm walletoffsets;
echo "Now try to load each of the test dat files."
echo "Sometimes they need to be loaded twice.";
echo "Ignore any errors about addressbook being courrupted.";
