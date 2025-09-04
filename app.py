# app.py

import streamlit as st
import pandas as pd
import google.generativeai as genai
import json

# --- Configuration ---
st.set_page_config(page_title="Advanced CSV Analyst", layout="wide")
st.title("Advanced CSV Analyst 📈")

# It's recommended to set the API key using Streamlit's secrets management.
# For this example, we'll use a sidebar input for convenience.
with st.sidebar:
    st.header("Configuration")
    api_key = st.text_input("Enter your Gemini API Key:", type="password")
    
    if api_key:
        # NEW CODE FOR DEPLOYMENT
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])   
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
    
    st.markdown("---")
    st.header("About")
    st.markdown("""
    This app uses Google's Gemini Pro to analyze your uploaded CSV data. 
    You can ask questions, request summaries, and even ask it to generate visualizations.
    """)

# --- Functions ---
def get_gemini_response(prompt):
    """Sends a prompt to the Gemini API and returns the response."""
    try:
        response = model.generate_content(prompt)
        # Attempt to clean and parse the JSON response
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned_response)
    except Exception as e:
        st.error(f"An error occurred with the API call: {e}") # The only error line we need
        return None

def create_prompt(df, user_question, history):
    """Creates a detailed prompt for the Gemini model."""
    # Get a summary of the dataframe
    data_summary = f"""
    Here is a summary of the data:
    - Column Names: {', '.join(df.columns)}
    - Number of rows: {len(df)}
    - Data Description:
    {df.describe().to_string()}
    """
    
    # Format the chat history
    formatted_history = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history])

    prompt = f"""
    You are an expert data analyst. Your user has uploaded a CSV file and will ask questions about it.
    Analyze the data summary and the conversation history to answer the user's latest question.

    **Data Summary:**
    {data_summary}

    **Conversation History:**
    {formatted_history}

    **User's Latest Question:**
    {user_question}

    **Instructions for your response:**
    1.  Provide a clear, concise text answer in the "answer" field.
    2.  If the question can be better answered with a visualization, generate the necessary Python code using the Plotly library and the provided dataframe `df`. Place this code in the "python_code" field.
    3.  The Python code should create a Plotly figure object named 'fig'. For example: `import plotly.express as px; fig = px.bar(df, ...)`
    4.  Return your response as a single, valid JSON object with two keys: "answer" (string) and "python_code" (string, or null if no chart is needed).
    
    Example JSON response:
    {{
        "answer": "The average sales amount is $550.",
        "python_code": "import plotly.express as px; fig = px.histogram(df, x='Sales')"
    }}
    """
    return prompt

# --- Main App Logic ---

# Initialize session state for chat history and dataframe
if "messages" not in st.session_state:
    st.session_state.messages = []
if "dataframe" not in st.session_state:
    st.session_state.dataframe = None

# File uploader
uploaded_file = st.file_uploader("Upload your CSV file to get started", type="csv")

if uploaded_file is not None:
    # Read and store the dataframe in session state
    try:
        df = pd.read_csv(uploaded_file)
        st.session_state.dataframe = df
        # Clear previous chat history when a new file is uploaded
        st.session_state.messages = []
        st.success("File uploaded successfully! Here's a preview of your data:")
        st.dataframe(df.head())
    except Exception as e:
        st.error(f"Error reading file: {e}")
        st.session_state.dataframe = None

# Display chat messages and handle user input
if st.session_state.dataframe is not None:
    df = st.session_state.dataframe
    
    # Display existing chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "chart" in message and message["chart"] is not None:
                st.plotly_chart(message["chart"])
                
    # Get user input
    if prompt := st.chat_input("Ask a question about your data..."):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        print(f"--- DEBUG: User question: {prompt} ---")
        # Generate the full prompt for the model
        full_prompt = create_prompt(df, prompt, st.session_state.messages)

        # Get response from Gemini
        with st.spinner("Analyzing and generating response..."):
            if not api_key:
                st.error("Please enter your Gemini API key in the sidebar to proceed.")
            else:
                print("--- DEBUG: Calling Gemini API... ---")
                response_data = get_gemini_response(full_prompt)
                print(f"--- DEBUG: API response received: {response_data} ---")

                if response_data:
                    answer = response_data.get("answer", "I couldn't find a text answer.")
                    print(f"--- DEBUG: Parsed answer: {answer} ---")
                    python_code = response_data.get("python_code")
                    fig = None

                    # If there's python code, execute it
                    if python_code:
                        try:
                            # IMPORTANT: exec() can be dangerous. Only use in trusted environments.
                            # We are executing code generated by the AI model.
                            local_scope = {"df": df, "st": st}
                            exec(python_code, globals(), local_scope)
                            fig = local_scope.get('fig')
                        except Exception as e:
                            st.error(f"Error executing generated Python code: {e}")
                            answer += "\n\n_Note: I tried to generate a chart but encountered an error._"
                    
                    # Display the model's response and chart
                    with st.chat_message("assistant"):
                        st.markdown(answer)
                        if fig:
                            st.plotly_chart(fig)
                    
                    # Add model response to chat history
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": answer, 
                        "chart": fig
                    })

else:
    st.info("Please upload a CSV file to begin the analysis.")