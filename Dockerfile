FROM public.ecr.aws/lambda/python:3.12

# Install g++ (Amazon Linux 2023 uses dnf)
RUN dnf install -y gcc-c++ && dnf clean all

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY agents/ ./agents/
COPY main.py lambda.py ./

# Lambda handler entrypoint
CMD ["lambda.handler"]
