// static/main.js

document.addEventListener("DOMContentLoaded", () => {
    const inputField = document.getElementById("comment-input");
    const submitButton = document.getElementById("submit-btn");
    const feedbackYes = document.getElementById("feedback-yes");
    const feedbackNo = document.getElementById("feedback-no");
    const resultDiv = document.getElementById("result");
  
    // Submit user input 
    submitButton.addEventListener("click", () => {
      const comment = inputField.value.trim();
      if (!comment) return;
  
      fetch("/userInput", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
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
    });
  
    // Send User feedback
    feedbackYes.addEventListener("click", () => sendJudgment(true));
    feedbackNo.addEventListener("click", () => sendJudgment(false));
  
    function sendJudgment(isCorrect) {
      alert(
        isCorrect
          ? "Thanks for feedback, we are happy we get you☺️"
          : "Oops, sorry! We'll do better next time🫡"
      );
  
      fetch("/judgment", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ isCorrect })
      })
        .then(response => response.json())
        .then(data => console.log("Judgment submitted:", data))
        .catch(error => console.error("Error submitting judgment:", error));
    }

});