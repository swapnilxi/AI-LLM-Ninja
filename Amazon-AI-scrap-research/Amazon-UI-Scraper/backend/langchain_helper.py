import os
import pandas as pd
from langchain.llms import OpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.prompts import PromptTemplate
from langchain.chains import RetrievalQA
from langchain.text_splitter import CharacterTextSplitter
from langchain.document_loaders import DataFrameLoader

# Load environment variables for OpenAI API Key
os.environ['OPENAI_API_KEY'] = 'your-openai-api-key-here'

# Load your processed CSV data into a pandas DataFrame
def load_data(file_path):
    df = pd.read_csv(file_path)
    return df

# Prepare the data for LangChain using a DataFrame loader and text splitter
def prepare_data_for_langchain(df):
    # Convert DataFrame to a list of documents
    loader = DataFrameLoader(df, page_content_column='title')  # Change 'title' to the main column you're querying
    documents = loader.load()
    
    # Split text for better embeddings
    text_splitter = CharacterTextSplitter(chunk_size=200, chunk_overlap=20)
    docs = text_splitter.split_documents(documents)

    # Create OpenAI Embeddings and VectorStore
    embeddings = OpenAIEmbeddings()
    db = FAISS.from_documents(docs, embeddings)

    return db

# Create a LangChain QA chain for chatting with your data
def create_qa_chain(db):
    llm = OpenAI(temperature=0)  # OpenAI model for answering
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm, chain_type="stuff", retriever=db.as_retriever()
    )
    return qa_chain

# Chat with the data
def chat_with_data(qa_chain, query):
    result = qa_chain.run(query)
    return result

if __name__ == "__main__":
    # Load your CSV file
    file_path = 'path_to_your_csv_file.csv'
    df = load_data(file_path)

    # Prepare the data for LangChain
    db = prepare_data_for_langchain(df)

    # Create a QA chain for querying the data
    qa_chain = create_qa_chain(db)

    # Example chat interaction
    query = "What is the highest-rated product?"
    response = chat_with_data(qa_chain, query)
    print(f"Response: {response}")
