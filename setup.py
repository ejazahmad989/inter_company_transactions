from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

version = "0.0.1"

setup(
    name="inter_company_transactions",
    version=version,
    description="A custom ERPNext application that enables seamless inter-company transactions between related companies",
    author="Your Company",
    author_email="support@example.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)
