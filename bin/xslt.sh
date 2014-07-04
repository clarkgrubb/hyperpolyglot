#!/bin/bash

# TODO: fix so doesn't have to be run from root

SAXON_JAR=bin/saxon9he.jar
MATH_XSL=bin/math.xsl
MATH_PAGES=math_pages.txt
ROOTNAME=${1%%.wiki}

set -eu -o pipefail

if [[ $# -ne 1 ]]
then
    echo "USAGE: xslt.sh INPUT.xml"
    exit 1
fi

if grep '^'$ROOTNAME'$' $MATH_PAGES > /dev/null
then
    echo "INFO applying $MATH_XSL to $1" > /dev/stderr
    echo <<EOF
<!DOCTYPE doctypeName [
   <!ENTITY nbsp "&#160;">
]>
EOF
    java -cp ${SAXON_JAR} net.sf.saxon.Transform -xsl:${MATH_XSL} -s:$1
else
    cat $1
fi
