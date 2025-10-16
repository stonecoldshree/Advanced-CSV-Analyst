# app.py

import streamlit as st
import pandas as pd
import google.generativeai as genai
import json

# --- Page Configuration ---
st.set_page_config(
    page_title="Advanced CSV Analyst",
    page_icon="📊",
    layout="wide"
)

# --- Gemini API Configuration ---
# NOTE: This is the correct way to configure the API key for deployment.
# It reads the key from the secrets you set up on Streamlit Community Cloud.
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-pro')
except Exception as e:
    st.error(f"Error configuring the Gemini API: {e}", icon="🚨")
    st.info("Please make sure you have set up your GEMINI_API_KEY in the Streamlit secrets.", icon="🔑")
    st.stop()


# --- Helper Functions ---

def get_gemini_response(prompt):
    """
    Sends a prompt to the Gemini API and returns the parsed JSON response.
    Handles potential errors during the API call.
    """
    try:
        response = model.generate_content(prompt)
        # Clean the response to ensure it's valid JSON
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned_response)
    except Exception as e:
        st.error(f"An error occurred while communicating with the Gemini API: {e}", icon="🔥")
        return None

def create_prompt(df, user_question, history):
    """
    Creates a detailed and structured prompt for the Gemini model,
    including data summary, conversation history, and instructions.
    """
    # Get a summary of the dataframe
    data_summary = f"""
    Here is a summary of the data:
    - Column Names: {', '.join(df.columns)}
    - Number of rows: {len(df)}
    - Data Description (statistical summary):
    {df.describe(include='all').to_string()}
    """
    
    # Format the chat history for the prompt
    formatted_history = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history])

    prompt = f"""
    You are an expert data analyst AI. Your user has uploaded a CSV file and will ask questions about it.
    Analyze the data summary and the conversation history to answer the user's latest question.

    **Data Summary:**
    {data_summary}

    **Conversation History:**
    {formatted_history}

    **User's Latest Question:**
    {user_question}

    **Your Task & Instructions:**
    1.  Provide a clear, concise text answer to the user's question in the "answer" field.
    2.  If the question can be better answered with a visualization, generate the necessary Python code to create it using the Plotly library. The dataframe is available as a variable named `df`. Place this code in the "python_code" field.
    3.  The Python code must create a Plotly figure object named 'fig'. For example: `import plotly.express as px; fig = px.bar(df, ...)`
    4.  Return your response as a single, valid JSON object with two keys: "answer" (string) and "python_code" (string, or null if no chart is needed).
    """
    return prompt

# --- Main Application Logic ---

# Add a title and a sidebar with information
st.title("Advanced CSV Data Analyst 📊")
with st.sidebar:
    st.header("About")
    st.markdown("""
    This app uses Google's Gemini Pro to analyze your uploaded CSV data. 
    You can ask questions, request summaries, and even ask it to generate visualizations.
    """)
    st.markdown("---")
    st.header("How to Use")
    st.markdown("""
    1.  Upload your CSV file.
    2.  Wait for the data preview to load.
    3.  Ask a question about your data in the chat box below.
    """)

# Initialize session state for chat history and dataframe
if "messages" not in st.session_state:
    st.session_state.messages = []
if "dataframe" not in st.session_state:
    st.session_state.dataframe = None

# File uploader
uploaded_file = st.file_uploader("Upload your CSV file to get started", type="csv", label_visibility="collapsed")

if uploaded_file is not None:
    # Read and store the dataframe in session state if it's not already there
    if st.session_state.dataframe is None:
        try:
            df = pd.read_csv(uploaded_file)
            st.session_state.dataframe = df
            # Clear previous chat history when a new file is uploaded
            st.session_state.messages = []
            st.success("File uploaded successfully! Here's a preview of your data:", icon="✅")
            st.dataframe(df.head())
        except Exception as e:
            st.error(f"Error reading the file: {e}", icon="❌")
            st.session_state.dataframe = None

# Main chat interface logic
if st.session_state.dataframe is not None:
    df = st.session_state.dataframe
    
    # Display existing chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "chart" in message and message["chart"] is not None:
                st.plotly_chart(message["chart"], use_container_width=True)
                
    # Get new user input
    if prompt := st.chat_input("Ask a question about your data..."):
        # Add user message to history and display it
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate the full prompt for the model
        full_prompt = create_prompt(df, prompt, st.session_state.messages)

        # Get response from Gemini
        with st.spinner("Analyzing and generating response..."):
            response_data = get_gemini_response(full_prompt)

            if response_data:
                answer = response_data.get("answer", "I couldn't find a text answer.")
                python_code = response_data.get("python_code")
                fig = None

                # If there's python code, execute it to generate a chart
                if python_code:
                    try:
                        # SECURITY WARNING: exec() can be dangerous.
                        # It's used here to run AI-generated code.
                        local_scope = {"df": df, "st": st}
                        exec(python_code, globals(), local_scope)
                        fig = local_scope.get('fig')
                    except Exception as e:
                        st.error(f"Error executing generated Python code: {e}", icon="🐍")
                        answer += "\n\n_Note: I tried to generate a chart but encountered an error._"
                
                # Display the model's text answer and the chart (if created)
                with st.chat_message("assistant"):
                    st.markdown(answer)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
                
                # Add the complete assistant response to chat history
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": answer, 
                    "chart": fig
                })

else:
    st.info("Please upload a CSV file to begin the analysis.")


