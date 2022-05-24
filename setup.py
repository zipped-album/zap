from setuptools import setup


def get_version():
    """Get version and version_info from zap/__meta__.py file."""

    import os
    module_path = os.path.join(os.path.dirname('__file__'), 'zap',
                               '__meta__.py')

    import importlib.util
    spec = importlib.util.spec_from_file_location('__meta__', module_path)
    meta = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(meta)

    return meta.__version__

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name = 'Zipped Album Player',
    description = \
    'Zipped Album Player (ZAP) - ' \
    'A simple Python-based cross-platform player for the Zipped Album format',
    author = 'Florian Krause',
    author_email = 'florian.krause@fladd.de',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url = 'https://github.com/zipped-album/zap',
    version = get_version(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
    ],
    packages = ['zap'],
    package_data = {'zap': ['*.png',
                            '*.ico']},
    python_requires=">=3.6",
    install_requires = ["pillow>=7.0.0,<=9.1.1",
                        "PyMuPDF>=1.17.4,<=1.19.6",
                        "audio-metadata==0.11.1",
                        "pyglet==1.5.26"],
    entry_points={
        'gui_scripts': [
            'zap = zap.__main__:run',
            'zipped-album-player = zap.__main__:run',
        ]
    }
)
