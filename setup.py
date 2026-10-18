from setuptools import find_packages, setup

with open('requirements.txt') as f:
	install_requires = [line.strip() for line in f if line.strip() and not line.startswith('#')]

# get version from __version__ variable in inter_company_transactions/__init__.py
from inter_company_transactions import __version__ as version

setup(
	name='inter_company_transactions',
	version=version,
	description='Enterprise Inter-Company Transactions for ERPNext (v14, v15 & v16 Compatible)',
	author='Ejaz Ahmed',
	author_email='ejazahmad989@gmail.com',
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires,
	classifiers=[
		'Framework :: Frappe',
		'Development Status :: 5 - Production/Stable',
		'Intended Audience :: Financial and Insurance Industry',
		'License :: OSI Approved :: MIT License',
		'Programming Language :: Python :: 3 :: Only',
		'Programming Language :: Python :: 3.10',
		'Programming Language :: Python :: 3.11',
		'Programming Language :: Python :: 3.12',
		'Topic :: Office/Business :: Financial :: Accounting',
	]
)
