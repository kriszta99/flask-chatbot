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
    let chatContent = className === "outgoing" ? `<p></p>` : `<span class="material symbols-outlined">smart_toy</span><p></p>`;
    chatLi.innerHTML = chatContent;
    chatLi.querySelector("p").textContent = message;
    return chatLi;
}

const handleChat = () => {
    // get user entered message and remove extra whitespace
    userMessage = chatInput.value.trim();
    if(!userMessage) return;
    // clear the input textarea and set its height to default
    chatInput.value = "";
    chatInput.style.height = `${inputInitHeight}px`;

    //append the user's message to the chatbox 
    chatbox.appendChild(createChatLi(userMessage, "outgoing"));
    chatbox.scrollTo(0, chatbox.scrollHeight);


    setTimeout(() => {
        // Display "Thinking..." message while waiting for the response
        const incomingChatLi = createChatLi("Thinking...", "incoming");
        chatbox.appendChild(incomingChatLi);
        chatbox.scrollTo(0, chatbox.scrollHeight);
    },600);

}
chatInput.addEventListener("input", () => {
    // adjust the height of the input textarea based on its content
    chatInput.style.height = `${inputInitHeight}px`;
    chatInput.style.height = `${chatInput.scrollHeight}px`;
  });

  chatInput.addEventListener("keydown", (e) => {
    // if enter key is predded without Shift key and the window
    //width is greater then 800px, handle the chat
    if(e.key === "Enter" && !e.shiftKey && windiw.innerWidth > 800){
        e.preventDefault();
        handleChat();
    }
   
  });
sendChatBtn.addEventListener("click",handleChat);
chatbotToggler.addEventListener("click", ()=> document.body.classList.toggle("show-chatbot"));
chatbotCloseBtn.addEventListener("click", () => document.body.classList.remove("show-chatbo"));