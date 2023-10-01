let form = document.getElementById('form')

chatSocket.onmessage = (e) => {
  let data = JSON.parse(e.data)
  if (data['type'] == 'message') {
    if (data['user'] == user) {
      var msg = $(
        `<div class="media mb-1 justify-content-end d-flex">
          <div class="media-body text-right ps-5">
            <div class="alert alert-primary message" role="alert">
              <span>${data['message']}</span>
              <small class="small text-muted position-absolute bottom-0 end-0 pe-2 pt-5">${data['time']}</small>
            </div>
          </div>
          <div class="img-fluid">
            <img class="ms-2 mt-1 chat-user-profile" src="${user_avatar}" alt="">
          </div>
        </div>`
      );
    }
    else if (data['user'] == partner) {
      var msg = $(
        `<div class="media mb-1 d-flex">
          <div class="img-fluid">
            <img class="me-2 mt-1 chat-user-profile" src="${partner_avatar}" alt="">
          </div>
          <div class="media-body pe-5">
            <div class="alert alert-success message" role="alert">
              <span>${data['message']}</span>
              <small class="small text-muted position-absolute bottom-0 end-0 pe-2 pt-5">${data['time']}</small>
            </div>
          </div>
        </div>`
      );
    }
    $('#scrollable').append(msg);
    scroll()
  }
}
function updatePartnerStatus(status) {
  const partnerStatusElement = document.getElementById('status');
  if (status == 'online') {
    partnerStatusElement.innerHTML = `${partner} - <span class="text-success">online</span>`;
  } else {
    partnerStatusElement.innerHTML = `${partner} - <span class="text-danger">offline</span>`;
  }
}
updatePartnerStatus();
chatSocket.onmessage = (e) => {
  data = JSON.parse(e.data)
  if (data['type'] == 'status' & data['user'] == partner_email) {
    updatePartnerStatus(data['status'])
  }
}
chatSocket.onclose = function (e) {
  console.error('Chat socket closed unexpectedly');
};
form.addEventListener('submit', (e) => {
  e.preventDefault()
  let message = e.target.message.value
  chatSocket.send(JSON.stringify({ 'type': 'message','content': message }))
  form.reset()
})
function scroll() {
  var scrollingDiv = document.getElementById("scrollable");
  scrollingDiv.scrollTop = scrollingDiv.scrollHeight;
}
scroll()
window.scrollTo(0, document.body.scrollHeight);