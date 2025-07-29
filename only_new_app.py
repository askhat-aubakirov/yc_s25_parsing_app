import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import plotly.express as px
from collections import Counter
import matplotlib.pyplot as plt
from wordcloud import WordCloud


CSV_PATH = "clean_new_data.csv"

#utility functions

def load_existing_data():
    if os.path.exists(CSV_PATH):
        return pd.read_csv(CSV_PATH)
    return pd.DataFrame(columns=["Company Name", "Full Description", "YC Page", "Website", "LinkedIn URL", "Mentions YC S25"])

def setup_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(options=options)

def check_yc_s25_on_linkedin(driver, linkedin_url):
    if not linkedin_url:
        return 0, None
    try:
        driver.get(linkedin_url)
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        text = soup.get_text().lower()
        return (1 if "yc s25" in text else 0), text.strip()[:1000]
    except:
        return 0, None

def get_yc_company_list(driver):
    driver.get("https://www.ycombinator.com/companies?batch=Summer%202025")
    WebDriverWait(driver, 15).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a._company_i9oky_355"))
    )

    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    companies = driver.find_elements(By.CSS_SELECTOR, "a._company_i9oky_355")
    yc_list = []
    for company in companies:
        try:
            name = company.find_element(By.CLASS_NAME, "_coName_i9oky_470").text
            link = company.get_attribute("href")
            yc_list.append({"Company Name": name, "YC Page": link})
        except:
            continue
    return pd.DataFrame(yc_list)

def scrape_new_companies(existing_df):
    driver = setup_driver()
    yc_list = get_yc_company_list(driver)
    existing_names = set(existing_df["Company Name"])
    new_companies = yc_list[~yc_list["Company Name"].isin(existing_names)]

    new_data = []
    for _, row in new_companies.iterrows():
        try:
            name, link = row["Company Name"], row["YC Page"]

            driver.execute_script("window.open('');")
            driver.switch_to.window(driver.window_handles[1])
            driver.get(link)

            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.prose"))
            )
            full_desc = driver.find_element(By.CSS_SELECTOR, "div.prose").text

            try:
                website = driver.find_element(By.XPATH, "//div[contains(@class, 'group-hover:underline')]").text.strip()
            except:
                website = None

            try:
                linkedin_url = driver.find_element(By.XPATH, "//a[contains(@aria-label, 'LinkedIn profile')]").get_attribute("href")
            except:
                linkedin_url = None

            flag, _ = check_yc_s25_on_linkedin(driver, linkedin_url)

            new_data.append({
                "Company Name": name,
                "Full Description": full_desc,
                "YC Page": link,
                "Website": website,
                "LinkedIn URL": linkedin_url,
                "Mentions YC S25": flag
            })

            driver.close()
            driver.switch_to.window(driver.window_handles[0])
        except Exception as e:
            print(f"Error processing {row['Company Name']}: {e}")
            driver.switch_to.window(driver.window_handles[0])
            continue

    driver.quit()
    return pd.DataFrame(new_data)

def update_data():
    existing = load_existing_data()
    new = scrape_new_companies(existing)
    if not new.empty:
        df = pd.concat([existing, new]).drop_duplicates(subset="Company Name", keep="last")
        df.to_csv(CSV_PATH, index=False, encoding="utf-8")
        return df
    return existing

#additional functions to visualise data
def show_summary(df):
    st.header("📊 Summary Statistics")
    col1, col2, col3 = st.columns(3)
    
    col1.metric("Total Companies", len(df))
    col2.metric("With Website", df['Website'].notna().sum())
    col3.metric("Mentions YC S25", df['Mentions YC S25'].sum())

    st.markdown("---")


def show_linkedin_mentions_chart(df):
    st.subheader("🔍 LinkedIn Mentions of 'YC S25'")

    counts = df['Mentions YC S25'].value_counts().rename(index={0: "No", 1: "Yes"}).reset_index()
    counts.columns = ['Mentioned', 'Count']  # Rename for plotly compatibility

    fig = px.pie(
        counts,
        names='Mentioned',
        values='Count',
        title="Companies Mentioning 'YC S25' on LinkedIn",
        hole=0.4
    )
    st.plotly_chart(fig, use_container_width=True)
    fig.update_traces(textinfo='percent+label')


def filter_by_name(df):
    st.subheader("🔎 Search Companies by Name")
    search_term = st.text_input("Enter company name:")
    if search_term:
        filtered_df = df[df["Company Name"].str.contains(search_term, case=False)]
        st.dataframe(filtered_df, use_container_width=True)

def download_button(df):
    st.download_button("📥 Download Data as CSV", df.to_csv(index=False), file_name="yc_s25_companies.csv", mime="text/csv")


def show_common_words(df):
    st.subheader("🧠 Common Words in Full Descriptions")

    all_text = " ".join(df["Full Description"].dropna().values).lower()
    stopwords = set(["the", "and", "with", "for", "that", "this", "are", "from", "our", "its", "we", "on", "a", "to", "in"])
    words = [word.strip(".,()[]").lower() for word in all_text.split() if word.lower() not in stopwords and len(word) > 3]
    word_freq = Counter(words)

    wordcloud = WordCloud(width=800, height=400, background_color="white").generate_from_frequencies(word_freq)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.imshow(wordcloud, interpolation="bilinear")
    ax.axis("off")
    st.pyplot(fig)

#func to share my contacts
def show_contact_info():
    st.markdown("## 📬 Contacts")
    st.markdown("""
    **Created by:** Askhat Aubakirov  
    **Email:** [askhat.aub.work@gmail.com](askhat.aub.work@gmail.com)  
    **LinkedIn:** [linkedin.com/in/askhattio](https://linkedin.com/in/askhattio)  
    **GitHub:** [https://github.com/askhat-aubakirov](https://github.com/askhat-aubakirov)  
    """)


#the app
st.set_page_config("🚀 YC S25 Scraper", layout="wide")
st.title("🚀 YC Summer 2025 Companies Tracker")

show_contact_info()

if "df" not in st.session_state:
    st.session_state.df = load_existing_data()
    st.session_state.last_updated = datetime.now()

st.caption(f"Last update: {st.session_state.last_updated.strftime('%Y-%m-%d %H:%M:%S')}")



if st.button("🔄 Update Now (Scrape New Companies)"):
    with st.spinner("Scraping in progress..."):
        df_updated = update_data()
        st.session_state.df = df_updated
        st.session_state.last_updated = datetime.now()
    st.success("✅ Updated successfully!")

st.dataframe(st.session_state.df, use_container_width=True)

show_summary(st.session_state.df)
show_linkedin_mentions_chart(st.session_state.df)
filter_by_name(st.session_state.df)
show_common_words(st.session_state.df)
download_button(st.session_state.df)