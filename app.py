from dotenv import load_dotenv

load_dotenv()

import streamlit as st
import os
import io
import base64
from PIL import Image
import pdf2image
import google.generativeai as genai

genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))

def get_gemini_response(input,pdf_content,prompt):
    model=genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content([input,pdf_content[0],prompt])
    return response.text

def input_pdf_setup(uploaded_file):
    if uploaded_file is not None:
    ##convert pdf --> image

        images=pdf2image.convert_from_bytes(uploaded_file.read())

        first_page = images[0]

        ##convert to bytes

        img_byte_arr=io.BytesIO()
        first_page.save(img_byte_arr,format='JPEG')
        img_byte_arr=img_byte_arr.getvalue()

        pdf_parts = [
        {
            "mime_type":"image/jpeg",
            "data":base64.b64encode(img_byte_arr).decode()
        }
        ]
        return pdf_parts
    else:
        raise FileNotFoundError("No file uploaded ")

##streamlit app

st.set_page_config(page_title='ATS RESUME EXPERT')
st.header('ATS TRACKING SYSTEM')
input_text=st.text_area("Job Description : ",key="input")
uploaded_file=st.file_uploader("Upload Your Resume(PDF)..... ",type=['pdf'])

if uploaded_file is not None:
    st.write("PDF Uploaded Successfully!")

submit1 = st.button("Tell me Summary of Resume")
submit2 = st.button("How can I Improvise my Skills")
submit3 = st.button("Missing Keywords")
submit4 = st.button("Percentage Match")


input_prompt1 =""" 
You are an experienced HR with Technical Experience in the field of any one of Data Science , Full stack , Web Development Devops, Data Analyst
your task is to review the provided resume against the job description for these various profiles.
Please share your professional evaluation on whether the candidates profile align with the role
Highlight the candidates strengths and weaknesses in relation to the job description.
"""

input_prompt2=""" 
You are an experienced Technical Human Resource Manager,your task is to review the provided resume against the job description. 
Share your insights on the candidates suitability for the role  from and HR as well as from an Technical person.
"""

input_prompt3=""" 
You are an experienced Technical Human Resource Manager,your task is to review the provided resume against the job description. 
Highlight the keywords that are missing from  the applicants resume in relation to the specified job requirements. 
"""

input_prompt4 = """
You are an skilled ATS (Applicant Tracking System) scanner with a deep understanding of Data Science , Full stack , Web Development Devops, Data Analyst and ATS functionality, 
your task is to evaluate the resume against the provided job description. give me the percentage of match if the resume matches
the job description. First the output should come as percentage and then keywords missing and last final thoughts.
"""

if submit1:
    if uploaded_file is not None:
        pdf_content=input_pdf_setup(uploaded_file)
        response=get_gemini_response(input_prompt1,pdf_content,input_text)
        st.subheader("The Response is")
        st.write(response)
    else:
        st.write("Please upload the resume")
elif submit2:
    if uploaded_file is not None:
        pdf_content=input_pdf_setup(uploaded_file)
        response=get_gemini_response(input_prompt2,pdf_content,input_text)
        st.subheader("The Response is")
        st.write(response)
    else:
        st.write("Please upload the resume")

elif submit3:
    if uploaded_file is not None:
        pdf_content=input_pdf_setup(uploaded_file)
        response=get_gemini_response(input_prompt3,pdf_content,input_text)
        st.subheader("The Response is")
        st.write(response)
    else:
        st.write("Please upload the resume")
elif submit4:
    if uploaded_file is not None:
        pdf_content=input_pdf_setup(uploaded_file)
        response=get_gemini_response(input_prompt4,pdf_content,input_text)
        st.subheader("The Response is")
        st.write(response)
    else:
        st.write("Please upload the resume")
else: 
    st.write("Please upload the resume")
