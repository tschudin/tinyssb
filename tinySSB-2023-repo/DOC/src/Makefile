# Makefile

TARGETDIR=..

%.pdf: %.md
	pandoc --include-in-header helvet.tex \
	-fmarkdown-implicit_figures \
	-V 'mainfont=Helvetica' \
	-V 'geometry: margin=3cm' \
	$*.md \
	-o $(TARGETDIR)/$*.pdf

# ----------------------------------------------------------------------

all:    bipf.pdf

clean:
	rm -rf *~

# eof

