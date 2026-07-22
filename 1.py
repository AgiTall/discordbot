import os

def get_file_size(file_path):
    """Returns the size of the file in bytes."""
    if os.path.isfile(file_path):
        return os.path.getsize(file_path)
    else:
        raise FileNotFoundError(f"The file {file_path} does not exist.")

 def main():
    file_path = input("Enter the path of the file: ")
    try:
        size = get_file_size(file_path)
        print(f"The size of the file is: {size} bytes.")
    except FileNotFoundError as e:
        print(e)

if __name__ == "__main__":
    main()