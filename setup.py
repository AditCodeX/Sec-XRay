from setuptools import setup

setup(
    name="sec-xray",
    version="1.0.0",
    description="Passive & Dynamic SPA/JS Reconnaissance Engine",
    author="Aditya Agung Triwibowo",
    url="https://github.com/AditCodeX/Sec-XRay",
    py_modules=["sec_xray"],
    install_requires=[
        "requests",
        "playwright>=1.40.0",
        "playwright-stealth>=2.0.0",
        "rich>=13.0.0",
    ],
    entry_points={
        "console_scripts": [
            "sec-xray=sec_xray:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Topic :: Security",
    ],
    python_requires=">=3.8",
)
