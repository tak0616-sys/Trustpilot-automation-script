import os
import subprocess
import sys


def run_command(command, check=True):
    """Run a command in the shell."""
    result = subprocess.run(
        command,
        shell=True,
        check=check,
        text=True,
        capture_output=True,
        cwd=os.path.dirname(__file__),
    )
    return result


def is_first_run(pip):
    proc = lambda reqs: [x.strip() for x in reqs.split("\n") if x]
    with open(os.path.join(os.path.dirname(__file__), "requirements.txt")) as f:
        requirements = f.read()
    alread_reqs = proc(run_command(f"{pip} freeze").stdout)
    for req in proc(requirements):
        if not req in alread_reqs:
            print(f"{req} not installed, installing missing pacakges...")
            return True
    return False


def main():
    # Check if 'venv' directory exists, if not, create and activate it
    pip = "pip"
    """if not os.path.isdir("venv"):
        print("Creating virtual environment...")
        run_command("python -m venv venv")
        pip = os.path.join("venv", "Scripts", "pip")"""

    # Fetch latest commits from remote
    changed_files = ""
    try:
        print("Fetching latest commits from remote...")
        run_command("git fetch origin")

        # Check for changes in requirements.txt
        print("Checking for changes in requirements.txt...")
        changed_files = run_command(
            "git diff origin/main -- requirements.txt", check=False
        ).stdout
        print("Pulling changes...")
        run_command(f"git pull")
        # If requirements.txt has changed, install dependencies
    except subprocess.CalledProcessError:
        print("Can't retrieve changes, maybe GIT not ocnfigured?")
    if "requirements.txt" in changed_files or is_first_run(pip):
        print("requirements.txt changed, installing dependencies...")
        run_command(f"{pip} install -r requirements.txt")


if __name__ == "__main__":
    main()
