from setuptools import setup, find_packages

setup(
    name="oms_shared",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pydantic>=2.0",
        "confluent-kafka",
        "structlog",
        "prometheus-client",
        "opentelemetry-sdk",
        "opentelemetry-exporter-otlp-proto-grpc",
        "opentelemetry-instrumentation",
    ],
)
