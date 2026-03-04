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

ENTRYPOINT ["sh", "-c", "streamlit run src/visualisation/dashboard.py --server.port=${PORT:-8501} --server.address=0.0.0.0 --server.headless=true"]
