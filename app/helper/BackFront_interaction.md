### 1. **Backend Configuration**

The backend is set up to serve the questions dynamically from the `questions.yaml` file. This is done using a FastAPI endpoint (`/config`), which reads the YAML file and returns the questions in a JSON format.

#### **Explanation of the Backend Endpoint**

Here's a breakdown of how the backend works:

1. **FastAPI Endpoint** (`/api/v1/questionnaire/config`):

   - The backend uses the `yaml` library to read the `questions.yaml` file from the server’s file system.
   - The questions are then parsed and converted into a dictionary format, where the keys are question IDs, and the values are the details of the question (question text, options, type, etc.).
   - This allows the frontend to fetch the questions and build the questionnaire dynamically based on the backend configuration.

   ```python
   @router.get("/config", response_model=Dict[str, Any])
   def get_questionnaire_config():
       """
       Reads the questions.yaml file and returns its content as JSON.
       This allows the frontend to dynamically build the questionnaire.
       """
       try:
           with open("data/questions.yaml", 'r', encoding='utf-8') as f:
               questions = yaml.safe_load(f)
               return questions.get('questions', {})
       except FileNotFoundError:
           raise HTTPException(status_code=404, detail="Questionnaire configuration file not found.")
       except yaml.YAMLError:
           raise HTTPException(status_code=500, detail="Error parsing the questionnaire configuration file.")
   ```

2. **Questionnaire Structure**:

   - `questions.yaml` contains a structure where each question has an `id`, `question text`, `type` (e.g., multiple choice, scale, body map, etc.), and any additional fields like `options` or `follow_up` (for adaptive questions).
   - For example:

     ```yaml
     questions:
       main_concern:
         question: "Quelles sont vos préoccupations principales actuellement ?"
         type: "multiple_choice"
         options:
           - label: "Douleurs physiques"
             value: "physical_pain"
           - label: "Stress et anxiété"
             value: "stress_anxiety"
       pain_location:
         question: "Où ressentez-vous des douleurs ?"
         type: "body_map"
         follow_up_conditions:
           back: "back_pain_specific"
     ```

### 2. **Frontend Integration**

The frontend JavaScript has been updated to fetch these questions from the backend and render them on the user interface dynamically. Let's break down the key logic:

#### **Step-by-step Process in the Frontend**:

1. **Loading Questions**:

   - When the application starts (`init()`), the front-end makes an HTTP request to the backend endpoint (`/api/v1/questionnaire/config`) to retrieve the list of questions.
   - It then stores these questions in `this.state.questions` and starts the questionnaire by rendering the first question.

   ```javascript
   async loadQuestions() {
       try {
           const response = await fetch('http://localhost:8000/api/v1/questionnaire/config');
           const questions = await response.json();
           this.state.questions = questions;  // Save questions data
           this.startQuestionnaire();
       } catch (error) {
           console.error('Error loading questions:', error);
           alert("Impossible de charger les questions.");
       }
   }
   ```

2. **Rendering Questions**:

   - The questions are rendered based on their type. For example:

     - If the question type is `multiple_choice`, it generates a set of checkboxes for each option.
     - If the question type is `single_choice`, it uses radio buttons for each option.

   - The question options (such as `Douleurs physiques`, `Stress et anxiété`, etc.) are rendered dynamically in the HTML.

   ```javascript
   renderNextQuestion() {
       const questionId = this.state.questionnaire.queue.shift();
       const question = this.state.questions[questionId];
       let html = `<h3 class="text-lg font-semibold text-slate-800 mb-4">${question.question}</h3>`;
       html += '<div class="space-y-3">';

       if (question.type === 'multiple_choice' || question.type === 'single_choice') {
           question.options.forEach(opt => {
               const inputType = question.type === 'single_choice' ? 'radio' : 'checkbox';
               html += `
                   <div>
                       <label class="flex items-center p-3 bg-white rounded-lg border border-slate-200 hover:bg-indigo-50 cursor-pointer">
                           <input type="${inputType}" name="q_option" value="${opt.value}" class="h-4 w-4 text-indigo-600 border-slate-300 focus:ring-indigo-500">
                           <span class="ml-3 text-slate-700">${opt.label}</span>
                       </label>
                   </div>
               `;
           });
       }

       html += '</div>';
       html += `<button onclick="app.answerQuestion('${questionId}')" class="mt-6 w-full bg-emerald-600 text-white font-semibold py-3 px-4 rounded-lg shadow-md hover:bg-emerald-700 transition">Suivant</button>`;

       this.elements.questionContainer.innerHTML = html;
   }
   ```

3. **Tracking and Submitting Responses**:

   - When the user answers a question, the selected answers are stored in `this.state.questionnaire.responses`, with the question ID as the key.
   - After each answer, the frontend checks if there are any follow-up questions based on the current answer. These follow-up questions are added to the queue to be asked next.

   ```javascript
   async answerQuestion(questionId) {
       const question = this.state.questions[questionId];
       const inputs = this.elements.questionContainer.querySelectorAll('input[name="q_option"]:checked');
       const responses = Array.from(inputs).map(input => input.value);

       this.state.questionnaire.responses[questionId] = question.type === 'single_choice' ? responses[0] : responses;

       let followUps = [];
       if (question.follow_up) {
           followUps.push(...question.follow_up);
       }
       if (question.follow_up_conditions) {
           responses.forEach(res => {
               if (question.follow_up_conditions[res]) {
                   followUps.push(question.follow_up_conditions[res]);
               }
           });
       }

       this.state.questionnaire.queue.unshift(...followUps);
       this.renderNextQuestion();
   }
   ```

4. **Submitting the Questionnaire**:

   - Once all the questions are answered, the user can submit the entire questionnaire, and the responses are sent to the backend for processing.
   - The backend analyzes the responses and returns a personalized recommendation.

   ```javascript
   async submitQuestionnaire() {
       const payload = {
           session_id: this.state.sessionId,
           responses: this.state.questionnaire.responses
       };

       await this.getRecommendation('/recommendations/questionnaire', payload);
   }
   ```

5. **Displaying the Results**:

   - Once the backend returns a recommendation, the front-end displays the recommended practice along with any AI-generated advice.

   ```javascript
   renderResults(data) {
       const practice = data.recommended_practice;
       let html = `
           <div class="text-center">
               <p class="text-indigo-600 font-semibold">Pratique Recommandée</p>
               <h2 class="text-3xl font-bold text-slate-900 mt-1">${practice.practice_name}</h2>
               <p class="text-sm text-slate-500 mt-1">Score de pertinence : ${(practice.relevance_score * 100).toFixed(0)}%</p>
           </div>
           <div class="prose prose-slate max-w-none text-left">
               ${this.parseMarkdown(data.generated_advice)}
           </div>
       `;
       this.elements.resultsContent.innerHTML = html;
   }
   ```

### 3. **Overall Flow**

- **User starts the questionnaire**: The front-end makes a request to the backend to load the list of questions.
- **User answers questions**: Based on the user's responses, the front-end dynamically renders follow-up questions.
- **Backend processes responses**: Once the questionnaire is complete, the front-end sends the responses to the backend for analysis and recommendation.
- **User sees recommendation**: The backend generates a personalized recommendation based on the answers and sends it back to the front-end, which displays it to the user.

---

### Conclusion

This setup creates a dynamic, interactive questionnaire where:

- The front-end is highly flexible, as it pulls the questions and options dynamically from the backend.
- The user answers the questions, and follow-up questions are determined by their responses.
- The backend processes the responses using NLP and recommendation logic to provide a personalized result, which is then displayed on the front-end.

This approach separates the concerns of the front-end and back-end, making it easier to update the questionnaire logic (by modifying the `questions.yaml` file) without changing the front-end.
