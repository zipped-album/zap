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

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

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
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    packages = ['zap'],
    package_data = {'zap': ['*.png',
                            '*.ico']},
    python_requires=">=3.6",
    install_requires = ['pillow==8.3.1',
                        'PyMuPDF==1.18.16',
                        'audio-metadata==0.11.1',
                        'pyglet==1.5.19',
                        ],
    entry_points={
        'gui_scripts': [
            'zap = zap.zap:run',
            'zipped-album-player = zap.zap:run',
        ]
    }
)
