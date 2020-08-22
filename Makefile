help:
	@echo '    init'
	@echo '        install all project dependencies'
	@echo '    test'
	@echo '        run all tests'
	@echo '    upload'
	@echo '        build and upload packages to private repo'

init:
	@echo 'Install python dependencies'
	poetry install

test:
	@echo 'Run all tests'
	poetry run  nosetests -s  skrules

upload:
	@echo 'Build and Upload packages to gemfury'
	rm -rf dist/
	poetry build
	curl -F skope-rules=@dist/$(shell poetry build | grep '.tar.gz' | cut -d' ' -f 4)  https://${GEMFURY_PUSH_TOKEN}@push.fury.io/xaipient/