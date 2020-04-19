import os
from setuptools import setup
from deflacue import VERSION


f = open(os.path.join(os.path.dirname(__file__), 'README.rst'))
README = f.read()
f.close()


setup(
    name='deflacue',
    version='.'.join(map(str, VERSION)),
    url='http://github.com/idlesign/deflacue',

    description='deflacue is a SoX based audio splitter to split audio CD '
                'images incorporated with .cue files',
    long_description=README,
    license='BSD 3-Clause License',

    author='Igor `idle sign` Starikov',
    author_email='idlesign@yandex.ru',

    packages=['deflacue'],
    include_package_data=True,
    zip_safe=False,

    entry_points={
        'console_scripts': [
            'deflacue = deflacue.script:run_deflacue',
        ],
    },

    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: BSD License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Topic :: Multimedia :: Sound/Audio :: Conversion',
    ],
)
