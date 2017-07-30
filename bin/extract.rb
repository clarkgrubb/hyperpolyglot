#!/usr/bin/env ruby

require 'nokogiri'

fail 'USAGE: extract.rb INPUT_XML MATH_LIST' if ARGV.length != 2

MATH_PAGES = File.open(ARGV[1]).readlines.map { |line| line.rstrip + '.math' }

math = MATH_PAGES.include?(ARGV[0])

noko = Nokogiri::HTML(File.open(ARGV[0]))

puts <<'EOF'
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html lang="en" xml:lang="en" xmlns="http://www.w3.org/1999/xhtml">
EOF

puts '<head>'
puts '<meta http-equiv="content-type" content="text/html;charset=UTF-8"/>'
puts '<link rel="icon" type="image/gif" href="/favicon.gif"/>'
puts '<link rel="apple-touch-icon" sizes="120x120" href="touch-icon-iphone-retina.png" />'
puts '<link rel="apple-touch-icon" sizes="152x152" href="touch-icon-ipad-retina.png" />'
noko.xpath('//head//title').each { |node| puts node.to_xhtml }
if math
  puts <<EOF
<script type="text/javascript"
  src="http://cdnjs.cloudflare.com/ajax/libs/mathjax/2.7.0/MathJax.js?config=TeX-AMS-MML_HTMLorMML">
</script>

EOF
end

puts <<EOF
<style type="text/css" id="internal-style">
@import url(hyperpolyglot.css);
</style>
<meta http-equiv="content-type" content="text/html;charset=UTF-8"/>
<meta http-equiv="content-language" content="en"/>
EOF
puts '</head>'

puts '<body>'
puts <<'EOF'
<div id="container-wrap-wrap">
  <div id="container-wrap">
    <div id="container">
      <div id="header">
        <h1><a href="/"><span>Hyperpolyglot</span></a></h1>
      </div>
      <div id="content-wrap">
        <div id="main-content">
EOF
noko.xpath('//div[@id="page-title"]').each { |node| puts node.to_xhtml }
noko.xpath('//div[@id="page-content"]').each { |node| puts node.to_xhtml }

puts <<'EOF'
        </div>
      </div>
      <div id="license-area" class="license-area">
        <a href="https://github.com/clarkgrubb/hyperpolyglot/issues">issue tracker</a> |
        content of this page licensed under
        <a rel="license" href="http://creativecommons.org/licenses/by-sa/3.0/">
        creative commons attribution-sharealike 3.0</a>
        <br>
      </div>
    </div>
  </div>
</div>

<script type="text/javascript">

  var _gaq = _gaq || [];
  _gaq.push(['_setAccount', 'UA-17129977-2']);
  _gaq.push(['_trackPageview']);

  (function() {
    var ga = document.createElement('script'); ga.type = 'text/javascript'; ga.async = true;
    ga.src = ('https:' == document.location.protocol ? 'https://ssl' : 'http://www') + '.google-analytics.com/ga.js';
    var s = document.getElementsByTagName('script')[0]; s.parentNode.insertBefore(ga, s);
  })();

</script>

</body>
EOF

puts '</html>'
