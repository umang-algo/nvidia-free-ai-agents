const askBtn = document.getElementById('ask-btn');
const questionInput = document.getElementById('question-input');
const answerBlock = document.getElementById('answer-block');
const sourceBlock = document.getElementById('source-block');

askBtn.addEventListener('click', async () => {
    const question = questionInput.value.trim();
    if (!question) {
        answerBlock.textContent = 'Please enter a question first.';
        return;
    }

    answerBlock.textContent = 'Thinking...';
    sourceBlock.textContent = '';

    try {
        const response = await fetch('/query', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ question })
        });

        if (!response.ok) {
            const errorText = await response.text();
            answerBlock.textContent = `Error: ${errorText}`;
            return;
        }

        const data = await response.json();
        answerBlock.textContent = data.answer || 'No answer returned.';
        sourceBlock.innerHTML = data.sources.length
            ? `<strong>Sources:</strong> ${data.sources.join(', ')}`
            : '';
    } catch (error) {
        answerBlock.textContent = `Request failed: ${error.message}`;
    }
});
