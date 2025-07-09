document.getElementById("uploadForm").addEventListener("submit", async function (e) {
  e.preventDefault();

  const formData = new FormData();
  formData.append("flow_file", document.getElementById("flowFile").files[0]);
  formData.append("example_file", document.getElementById("exampleFile").files[0]);
  formData.append("job_desc_file", document.getElementById("jobDescFile").files[0]);
  formData.append("job_detail_file", document.getElementById("jobDetailFile").files[0]);

  const loader = document.getElementById("loader");
  const resultSection = document.getElementById("resultSection");
  const downloadLink = document.getElementById("downloadLink");
  loader.style.display = "block";
  resultSection.style.display = "none";

  try {
    const response = await fetch("https://system-prompt-generator.onrender.com/generate/", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) throw new Error("Failed to generate prompt");

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);

    downloadLink.href = url;
    resultSection.style.display = "block";
  } catch (error) {
    alert("Something went wrong: " + error.message);
  } finally {
    loader.style.display = "none";
  }
});
