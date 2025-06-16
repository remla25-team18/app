// static/main.js

document.addEventListener("DOMContentLoaded", () => {
    const inputField = document.getElementById("comment-input");
    const submitButton = document.getElementById("submit-btn");
    const feedbackYes = document.getElementById("feedback-yes");
    const feedbackNo = document.getElementById("feedback-no");
    const resultDiv = document.getElementById("result");

    let sessionId;

    // a new sessionId is created for each page load
    sessionId = crypto.randomUUID();
    document.cookie = `sessionId=${sessionId}; path=/; SameSite=Lax`;

    feedbackYes.disabled = true;
    feedbackNo.disabled = true;
  
    // Submit user input 
    submitButton.addEventListener("click", () => {
      const comment = inputField.value.trim();
      if (!comment) return;
  
      fetch("/userInput", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ text: comment })
      })
        .then(response => response.json())
        .then(data => {
            console.log("Backend response:", data); // Log the entire response
            resultDiv.innerHTML = `
            <h4>Model Analysis: ${data.label}</h4>
            `;
        })
        .catch(error => console.error("Error:", error));

        feedbackYes.disabled = false;
        feedbackNo.disabled = false;
    });
  
    // Send User feedback
    feedbackYes.addEventListener("click", () => sendJudgment(true));
    feedbackNo.addEventListener("click", () => sendJudgment(false));
  
    function sendJudgment(isCorrect) {
      feedbackYes.disabled = true;
      feedbackNo.disabled = true;

      alert(
        isCorrect
          ? "Thanks for feedback, we are happy we get you☺️"
          : "Oops, sorry! We'll do better next time🫡"
      );
  
      fetch("/judgment", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ isCorrect })
      })
        .then(response => response.json())
        .then(data => console.log("Judgment submitted:", data))
        .catch(error => console.error("Error submitting judgment:", error));
    }

});