from setuptools import setup

install_requires = [
    'couchdb>=1.0.1',
    'gevent',
    'openprocurement_client',
    'restkit',
]


setup(
    name='bridge',
    version='0.0.1',
    packages=[
        'bridge',
    ],
    entry_points={
        'console_scripts': [
            'run_bridge = bridge.bridge:run',
        ]
    },
    install_requires=install_requires
)
