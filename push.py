from AWS_lambda import push

# push("question-3c9951ab-4f22-4d22-93dc-d15b8a702e14", "http://localhost:8080/api/questionBank/question/internal/save-test-cases-and-driver-code", "606ed6954bbb886956db587b")

# question_id = "question-76a4cd11-6062-4386-8b4e-a0b8fff0f6c3
question_id = "question-90e1696c-e3c6-41d6-9f69-e2e6ee708a9a"
push(question_id, "https://www.boardinfinity.com/cms-api/api/questionBank/question/internal/save-test-cases-and-driver-code", "606ed6954bbb886956db587b")