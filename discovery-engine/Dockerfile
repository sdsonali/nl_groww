FROM python:3.11-slim

WORKDIR /app

COPY requirements-deploy.txt .
RUN pip install --no-cache-dir -r requirements-deploy.txt

COPY . .

EXPOSE 7860

CMD ["sh", "-c", "streamlit run ${APP_FILE:-mvp.py} --server.port=7860 --server.address=0.0.0.0 --server.headless=true --browser.gatherUsageStats=false"]
