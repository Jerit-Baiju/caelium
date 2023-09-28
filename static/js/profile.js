document.addEventListener("DOMContentLoaded", function () {
  const editButton = document.querySelector("#edit-profile-button");
  const profilePicture = document.querySelector("#profile-picture");
  const saveChangesButton = document.querySelector("#save-changes-button");
  editButton.addEventListener("click", function () {
    const inputFields = document.querySelectorAll(".form-control");
    // Toggle the disabled attribute for each input field
    inputFields.forEach(function (input) {
      input.disabled = !input.disabled;
    });
    // Toggle the visibility of the "Edit your profile" and "Save Changes" buttons
    profilePicture.classList.toggle("d-none");
    editButton.classList.toggle("d-none");
    saveChangesButton.classList.toggle("d-none");
  });
});
