# 🏨 App – Restaurant Sentiment Analysis

This is a web application for restaurant review sentiment analysis. It provides a REST API and a simple web interface for analyzing user comments.

### ✨ Features

* Sentiment analysis of restaurant reviews
* REST API and web UI
* Prometheus-compatible metrics endpoint for monitoring

### 💻 Running Locally with Docker

1. **Build the Docker image with the version you want to test:**
   
   - Condition A: Green/Red buttons
   - Condition B: Yellow/Yellow buttons
  
   This can be set by modifying the `USE_TRUE_FALSE_CLASSES` varible in `.env`: 
   - `USE_TRUE_FALSE_CLASSES = true` for Condition A
   -  `USE_TRUE_FALSE_CLASSES = false` for Condition B

   ```bash
   docker build -t team18-app --build-arg USE_TRUE_FALSE_CLASSES=true .
   ```

2. **Run the Docker container:**

   ```bash
   docker run -p 4200:4200 -d --name team18-app-container team18-app
   ```

3. **Access the application:**

   * Web UI: [http://localhost:4200](http://localhost:4200)
   * Metrics: [http://localhost:4200/metrics](http://localhost:4200/metrics)

4. **Clean up environment after use:**

   ```bash
   docker stop team18-app-container  # Stop the container
   docker rm team18-app-container    # Remove the container
   docker rmi team18-app  # Optionally remove the image
   ```