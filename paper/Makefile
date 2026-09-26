# latexmk drives the bibtex/rerun cycle; pdflatex alone needs three passes and silently gets it wrong.
PAPER = main
all:
	latexmk -pdf -interaction=nonstopmode -halt-on-error $(PAPER).tex
arxiv:
	python3 make_arxiv.py
clean:
	latexmk -C $(PAPER).tex
watch:
	latexmk -pdf -pvc -interaction=nonstopmode $(PAPER).tex
.PHONY: all arxiv clean watch
