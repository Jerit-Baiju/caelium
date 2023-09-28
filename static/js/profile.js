document.addEventListener("DOMContentLoaded", function () {
  const profileForm = document.querySelector("#profile-form");
  const editButton = document.querySelector("#edit-profile-button");
  const saveChangesButton = document.querySelector("#save-changes-button");
  const backButton = document.querySelector('#back-button')
  const inputFields = profileForm.querySelectorAll(".form-control");
  
  function checkForChanges() {
    const inputFields = profileForm.querySelectorAll(".form-control");
    let hasChanges = false;
    inputFields.forEach(function (input) {
      if (input.value !== input.defaultValue) {
        hasChanges = true;
        return;
      }
    });
    if (hasChanges) {
      saveChangesButton.classList.remove("d-none");
    } else {
      saveChangesButton.classList.add("d-none");
    }
  }
  profileForm.addEventListener("input", checkForChanges);
  editButton.addEventListener("click", function () {
    inputFields.forEach(function (input) {
      input.disabled = !input.disabled;
    });
    editButton.classList.toggle("d-none");
    backButton.classList.toggle("d-none")
  });
  backButton.addEventListener("click", function () {
    inputFields.forEach(function (input) {
      input.disabled = !input.disabled;
    });
    editButton.classList.toggle("d-none");
    backButton.classList.toggle("d-none")
  })
});