all: build

build:
	python3 -m build

test-upload:
	python3 -m twine upload --repository testpypi dist/*

upload:
	python3 -m twine upload dist/*

test-clean:
	rm -rf dist 
	pip uninstall dbs-todo

clean:
	rm -rf dist

test-install: build
	#pip install -i https://testpypi.org/simple/ --no-deps --upgrade dbs-todo
	pip install --user --force-reinstall --no-deps --upgrade dist/dbs_todo-*-any.whl

install:
	pip install dbs-todo
