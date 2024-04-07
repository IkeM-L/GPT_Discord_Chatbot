import docker
import requests


class DockerPythonExecutor:
    """Runs the given Python code in a Docker container and returns the output."""
    def __init__(self, image_name='python_runner', timeout=5):
        self.client = docker.from_env()
        self.image_name = image_name
        self.timeout = timeout

    def run_code(self, code):
        container = None
        # GPT4 has a bad habit of just putting the output variables as the last line
        # We need to make sure they are actually printed out
        code = self.ensure_print_statement(code)

        try:
            container = self.client.containers.run(self.image_name,
                                                   command=["python", "-c", code],
                                                   detach=True)
            # Wait for the container to finish
            result = container.wait(timeout=self.timeout)

            # Check if the container timed out
            if result.get('StatusCode', 0) != 0:
                return None, "Error: Code execution timed out or error occurred."

            output = container.logs()
            return output.decode('utf-8'), None
        # Return the specific error message to the user if possible
        except docker.errors.ContainerError as e:
            return None, f"Container error: {e.stderr.decode('utf-8')}"
        # Return a general error message if the error is unknown
        except Exception as e:
            return None, f"An error occurred: {e}"
        finally:
            # Clean up the container
            if container:
                try:
                    # Stop the container if it's still running
                    container.stop()
                except docker.errors.APIError:
                    # Handle the case where the container is already stopped
                    pass
                container.remove()

    @staticmethod
    def ensure_print_statement(code):
        """Ensure that the script prints something"""
        lines = code.strip().split('\n')

        # Check if any line contains a print statement
        has_print = any("print(" in line for line in lines)

        if not has_print and lines:
            # Add a print statement around the last line if it's not empty
            last_line = lines[-1].strip()
            if last_line:
                lines[-1] = f'print({last_line})'

        return '\n'.join(lines)
