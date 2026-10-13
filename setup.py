# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

with open('requirements.txt') as f:
	install_requires = [line.strip() for line in f if line.strip() and not line.startswith('#')]

# get version from __version__ variable in inter_company_transactions/__init__.py
from inter_company_transactions import __version__ as version

setup(
	name='inter_company_transactions',
	version=version,
	description='Enterprise Inter-Company Transactions for ERPNext',
	author='Rahil Ali',
	author_email='rahilali3311@gmail.com',
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)