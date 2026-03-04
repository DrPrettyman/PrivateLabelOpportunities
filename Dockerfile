FROM python:3.12-slim

WORKDIR /app

# Install only dashboard dependencies
COPY requirements-dashboard.txt .
RUN pip install --no-cache-dir -r requirements-dashboard.txt

# Copy dashboard code and data
COPY src/visualisation/dashboard.py src/visualisation/dashboard.py
COPY data/sample/ data/sample/
COPY .streamlit/ .streamlit/

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["streamlit", "run", "src/visualisation/dashboard.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
