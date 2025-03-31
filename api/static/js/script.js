const chatInput = document.querySelector(".chat-input textarea");
const sendChatBtn = document.querySelector(".chat-input span");
const chatbox = document.querySelector(".chatbox");
const chatbotToggler = document.querySelector(".chatbot-toggler");
const chatbotCloseBtn = document.querySelector(".close-btn");

let userMessage=null;
const inputInitHeight = chatInput.scrollHeight;


const createChatLi = (message, className) => {
    //Create a chat <li> element with passed message and className
    const chatLi = document.createElement("li");
    chatLi.classList.add("chat", `${className}`);
    let chatContent = className === "outgoing" ? `<p></p>` : `<span class="material-symbols-outlined">smart_toy</span><p></p>`;
    chatLi.innerHTML = chatContent;
    chatLi.querySelector("p").textContent = message;
    return chatLi;
}

const handleChat = async () => {
    // get user entered message and remove extra whitespace
    userMessage = chatInput.value.trim();
    if(!userMessage) return;
    // clear the input textarea and set its height to default
    chatInput.value = "";
    chatInput.style.height = `${inputInitHeight}px`;

    //append the user's message to the chatbox 
    chatbox.appendChild(createChatLi(userMessage, "outgoing"));
    chatbox.scrollTo(0, chatbox.scrollHeight);

    /*setTimeout(() => {
        // Display "Thinking..." message while waiting for the response
        const incomingChatLi = createChatLi("Thinking...", "incoming");
        chatbox.appendChild(incomingChatLi);
        chatbox.scrollTo(0, chatbox.scrollHeight);
    },600)
    */
    const incomingChatLi = createChatLi("Gondolkodom...", "incoming");
    chatbox.appendChild(incomingChatLi);
    chatbox.scrollTo(0, chatbox.scrollHeight);
    try {
        const response = await fetch('/', {  // Ide küldjük a kérést
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: userMessage })
        });
    
        const data = await response.json();
        console.log("Válasz:", data.answer);  // Kiírjuk a választ a konzolra (debugging célból)
    
        // Most az érkező válasz megjelenítése a chatboxban
        chatbox.removeChild(incomingChatLi);
        chatbox.appendChild(createChatLi(data.answer, "incoming"));  // Itt jelenik meg a válasz
        chatbox.scrollTo(0, chatbox.scrollHeight);
    
    } catch (error) {
        console.error("Hiba történt:", error);
    }
    

}
chatInput.addEventListener("input", () => {
    // adjust the height of the input textarea based on its content
    chatInput.style.height = `${inputInitHeight}px`;
    chatInput.style.height = `${chatInput.scrollHeight}px`;
  });

  chatInput.addEventListener("keydown", (e) => {
    // if enter key is predded without Shift key and the window
    //width is greater then 800px, handle the chat
    if(e.key === "Enter" && !e.shiftKey && window.innerWidth > 800){
        e.preventDefault();
        handleChat();
    }
   
  });
sendChatBtn.addEventListener("click",handleChat);
chatbotToggler.addEventListener("click", ()=> document.body.classList.toggle("show-chatbot"));
chatbotCloseBtn.addEventListener("click", () => document.body.classList.remove("show-chatbot"));