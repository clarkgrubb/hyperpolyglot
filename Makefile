MAKEFLAGS += --warn-undefined-variables
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail
.DEFAULT_GOAL := all
.DELETE_ON_ERROR:
.SUFFIXES:
.SECONDARY:

conf_dir := /etc/nginx/conf.d
domain := http://hyperpolyglot.wikidot.com
extract := ./bin/extract.rb
log_dir := /var/log/nginx
nginx := /etc/init.d/nginx
paths := start scripting scripting2 more cpp c pascal lisp ml logic stack
paths += shell data fortran computer-algebra unix-shells
paths += text-mode-editors version-control build multiplexers db
paths += lightweight-markup vector-graphics
paths += numerical-analysis math-notation distributions
math := $(patsubst %,%.math,$(paths))
html := $(patsubst %,master/%.html,$(paths))
wiki := $(patsubst %,%.wiki,$(paths))
markup := $(patsubst %,markup/%,$(paths))
errors := 404.html 500.html 502.html 503.html 504.html
icons := favicon.gif touch-icon-ipad-retina.png touch-icon-iphone-retina.png
robots := robots.txt
css := hyperpolyglot.css
static := $(errors) $(icons) $(robots) $(css)

.PHONY: install
install:
	cp ../hyperpolyglot-site-conf/site.conf $(conf_dir)
	$(nginx) reload

.PHONY: error
error:
	cat $(log_dir)/error.log

.PHONY: access
access:
	cat $(log_dir)/access.log

%.wiki:
	curl $(domain)/$* > $@

%.math: %.wiki
	./bin/xslt.sh $< > $@

master:
	mkdir -p $@

master/%.html: %.math | master
	$(extract) $< math_pages.txt > $@

master/sitemap.xml: $(html) | master
	./bin/sitemap.py master > $@

.PHONY: static | master
static:
	cp $(static) master

.PHONY: refresh
refresh: master/sitemap.xml static | master
	mv root root.$(shell date +%Y%m%d.%H%M)
	mv master root

markup:
	mkdir -p $@

markup/%: | markup
	./bin/page_content.py --page=$* --download > $@

.PHONY:
download: $(markup)

.PHONY: instructions
instructions:
	@echo
	@echo '------------------------------------------------------------------------------'
	@echo '  Go to '
	@echo
	@echo '    http://hyperpolyglot.wikidot.com/_admin/'
	@echo
	@echo '  and set'
	@echo
	@echo '    Security | Access policy'
	@echo
	@echo '  to "Closed" and click "Save changes".  Then run'
	@echo
	@echo '    $$ make clobber'
	@echo '    $$ make refresh'
	@echo
	@echo '  Remember to set the access policy back to  "Private and click "Save changes".'
	@echo
	@echo '  To edited markup to the wiki, use this command:'
	@echo
	@echo '    $$ ./bin/page_content.py --page=PAGE < markup/PAGE'
	@echo
	@echo '------------------------------------------------------------------------------'

.PHONY: all
all: instructions

.PHONY: clean.math
clean.math:
	-rm -f $(math)

.PHONY: clean.html
clean.html:
	-rm -f $(html)

.PHONY: clean
clean: clean.math clean.html

.PHONY: clobber
clobber: clean
	rm -f $(wiki)
