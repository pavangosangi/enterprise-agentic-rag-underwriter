from sentence_transformers import CrossEncoder

def main():
    print("Downloading and caching cross-encoder model...")
    # This will download the model to the default HuggingFace cache directory
    # so it is baked into the Docker image.
    model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
    print("Model cached successfully!")

if __name__ == "__main__":
    main()
