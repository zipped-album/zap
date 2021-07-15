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

setup(
    name = 'ZAP',
    description = 'Zipped Album Player',
    author = 'Florian Krause',
    author_email = 'florian.krause@fladd.de',
    version = get_version(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    packages = ['zap'],
    package_data = {'zap': ['*.png']},
    python_requires=">=3.6",
    install_requires = ['pillow==8.2.0',
                        'PyMuPDF==1.18.13',
                        'audio-metadata==0.11',
                        'pyglet==1.5.17',
                        ],
    entry_points={
        'gui_scripts': [
            'zap = zap.zap:run',
        ]
    }
)
