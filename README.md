# Set up

To run the app locally using Docker, use the following commands:

1. Build a Docker image:
    ```bash
    docker build -t app .
    ```

2. Run the Docker container and expose the port:
    ```bash
    docker run -p 4200:4200 -d --name app_container app
    ```

Once the container is running, you can access the app at [http://localhost:4200/](http://localhost:4200/).