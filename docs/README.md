Project documentation is built with [Sphinx](https://www.sphinx-doc.org/) using the [PyData Sphinx Theme](https://pydata-sphinx-theme.readthedocs.io/).

### Building Locally

Install the docs dependencies:

```bash
pip install -e . --group docs
```

Build the HTML output:

```bash
python -m sphinx -b html docs docs/_build/html
```

Open `docs/_build/html/index.html` in your browser to preview the result.

