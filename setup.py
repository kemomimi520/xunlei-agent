from setuptools import setup, find_packages

setup(
    name="xunlei-agent",
    version="1.0.0",
    description="Xunlei Cloud Drive CLI & Agent Tool for Linux",
    packages=find_packages(),
    install_requires=[
        "requests>=2.28.0",
        "qrcode>=7.4.0",
        "playwright>=1.40.0",
    ],
    entry_points={
        "console_scripts": [
            "xunlei-agent=xunlei_agent.cli:main",
            "xl-pan=xunlei_agent.cli:main",
        ],
    },
    python_requires=">=3.8",
)
