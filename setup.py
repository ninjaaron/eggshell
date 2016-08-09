from setuptools import setup
try:
    import fastentrypoints
except ImportError:
    from urllib import request
    fastep = request.urlopen('https://raw.githubusercontent.com/ninjaaron/fast-entry_points/master/fastentrypoints.py')
    namespace = {}
    exec(fastep.read(), namespace)

setup(
    name='eggshell',
    version='0.1',
    description='a command shell with python syntax',
    long_description=open('README.rst').read(),
    url='https://github.com/ninjaaron/eggshell',
    author='Aaron Christianson',
    author_email='ninjaaron@gmail.com',
    keywords='pipe shell',
    install_requires='easyproc>=0.3.2',
    entry_points={'console_scripts': ['eggshell = eggshell:main']},
    packages = ['eggshell'],
    classifiers=['Programming Language :: Python'],)
