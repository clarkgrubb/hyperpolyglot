
<xsl:stylesheet version="2.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

  <xsl:output method="html" indent="no"/>

  <xsl:attribute-set name="class-math-inline">
    <xsl:attribute name="class">math-inline</xsl:attribute>
  </xsl:attribute-set>

  <xsl:attribute-set name="style-display-block">
    <xsl:attribute name="style">display; block;</xsl:attribute>
  </xsl:attribute-set>

  <xsl:template match="@*|node()">
    <xsl:copy>
      <xsl:apply-templates select="@*|node()"/>
    </xsl:copy>
  </xsl:template>
  
  <xsl:template match="*:br">
    <xsl:element name="br" namespace="http://www.w3.org/1999/xhtml"/>
  </xsl:template>

  <xsl:template match="*:span[@class='math-inline']">
    <xsl:element name="span"
                 namespace="http://www.w3.org/1999/xhtml"
                 use-attribute-sets="class-math-inline">
      $<xsl:value-of select="."/>$
    </xsl:element>
  </xsl:template>

  <xsl:template match="*:span[@class='equation-number']"/>
  
  <xsl:template match="*:div[@class='math-equation']">
    <xsl:element name="div"
                 namespace="http://www.w3.org/1999/xhtml"
                 use-attribute-sets="class-math-inline style-display-block">
      $$<xsl:value-of select="."/>$$
    </xsl:element>
  </xsl:template>

</xsl:stylesheet>
