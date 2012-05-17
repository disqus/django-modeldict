test:
	pep8 --exclude=migrations --ignore=E501,E225 modeldict || exit 1
	pyflakes -x W modeldict || exit 1
	coverage run --include=modeldict/* setup.py test && \
	coverage html --omit=*/migrations/* -d cover
