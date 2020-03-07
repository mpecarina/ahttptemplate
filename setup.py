from setuptools import setup, find_packages
import os

with open(os.path.join("./version.txt")) as version_file:
    version_from_file = version_file.read().strip()

with open("./requirements.txt") as f_required:
    required = f_required.read().splitlines()

# with open("./test_requirements.txt") as f_tests:
#     required_for_tests = f_tests.read().splitlines()

setup(
    name="ahttptemplate",
    url="https://github.com/mpecarina/ahttptemplate.git",
    author="mpecarina",
    license="Apache 2.0",
    author_email="mattp@hbci.com",
    packages=find_packages(),
    install_requires=required,
    # tests_require=required_for_tests,
    version=version_from_file,
    description="AioHTTP Template Package"
                "RESTful API Boilerplate",
    include_package_data = True,
    keywords="asyncio rest api template",
    classifiers=[
        "Development Status :: 5 - Draft",
        "Programming Language :: Python :: 3.8",
        "Topic :: Software Development :: Libraries",
        "License :: OSI Approved :: Apache Software License",
    ]
)
