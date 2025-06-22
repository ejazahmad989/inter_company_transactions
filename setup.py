# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

with open('requirements.txt') as f:
	install_requires = f.read().strip().split('\n')

# get version from __version__ variable in inter_company_transactions/__init__.py
from inter_company_transactions import __version__ as version

setup(
	name='inter_company_transactions',
	version=version,
	description='A custom app for handling inter-company transactions',
	author='Your Company',
	author_email='your@example.com',
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)