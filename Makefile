help:
	@echo '    init'
	@echo '        install all project dependencies'
	@echo '    test'
	@echo '        run all tests'

init:
	@echo 'Install python dependencies'
	poetry install

test:
	@echo 'Run all tests'
	poetry run  nosetests -s  skrules