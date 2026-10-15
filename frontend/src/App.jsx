import React, { useState, useEffect } from "react";

export default function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [currentResult, setCurrentResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([]);

  // Fetch past meal logs from Python backend on mount
  useEffect(() => {
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    try {
      const response = await fetch("http://localhost:8000/api/meal-history");
      const data = await response.json();
      setHistory(data);
    } catch (err) {
      console.error("Failed to fetch history:", err);
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setSelectedFile(file);
      setPreviewUrl(URL.createObjectURL(file));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedFile) return;

    setLoading(true);
    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const response = await fetch("http://localhost:8000/api/analyze-food", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) throw new Error("Analysis failed");

      const data = await response.json();
      setCurrentResult(data);
      fetchHistory(); // Refresh history table from SQLite database
    } catch (err) {
      console.error("Upload error:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: "800px", margin: "40px auto", fontFamily: "system-ui, sans-serif", padding: "0 20px" }}>
      <h1 style={{ textAlign: "center" }}>Smart Recipe & Macro Calculator</h1>

      {/* Form Upload Section */}
      <div style={{ border: "2px dashed #bbb", padding: "30px", textAlign: "center", borderRadius: "12px", background: "#fafafa" }}>
        <form onSubmit={handleSubmit}>
          <input type="file" accept="image/*" onChange={handleFileChange} />
          {previewUrl && (
            <div style={{ marginTop: "15px" }}>
              <img src={previewUrl} alt="Upload preview" style={{ maxHeight: "200px", borderRadius: "8px" }} />
            </div>
          )}
          <br />
          <button
            type="submit"
            disabled={!selectedFile || loading}
            style={{
              marginTop: "15px",
              padding: "10px 24px",
              background: loading ? "#ccc" : "#0070f3",
              color: "#fff",
              border: "none",
              borderRadius: "6px",
              cursor: "pointer",
              fontSize: "16px"
            }}
          >
            {loading ? "Analyzing Image with ML Model..." : "Calculate Macros"}
          </button>
        </form>
      </div>

      {/* Latest Analysis Result Card */}
      {currentResult && (
        <div style={{ marginTop: "25px", background: "#f0f8ff", padding: "20px", borderRadius: "8px", borderLeft: "5px solid #0070f3" }}>
          <h2>Detected Food: {currentResult.detected_food}</h2>
          <div style={{ display: "flex", gap: "20px", flexWrap: "wrap" }}>
            <p><strong>Calories:</strong> {currentResult.macros.calories} kcal</p>
            <p><strong>Protein:</strong> {currentResult.macros.protein}g</p>
            <p><strong>Carbs:</strong> {currentResult.macros.carbs}g</p>
            <p><strong>Fat:</strong> {currentResult.macros.fat}g</p>
          </div>
        </div>
      )}

      {/* Persistent History Log Table */}
      <h2 style={{ marginTop: "40px" }}>Meal Log History (Saved in Database)</h2>
      <table style={{ width: "100%", borderCollapse: "collapse", marginTop: "10px" }} border="1" cellPadding="10">
        <thead>
          <tr style={{ background: "#f4f4f4" }}>
            <th>ID</th>
            <th>Food Item</th>
            <th>Calories</th>
            <th>Protein (g)</th>
            <th>Carbs (g)</th>
            <th>Fat (g)</th>
          </tr>
        </thead>
        <tbody>
          {history.length === 0 ? (
            <tr>
              <td colSpan="6" style={{ textAlign: "center" }}>No logs saved yet. Upload an image above!</td>
            </tr>
          ) : (
            history.map((meal) => (
              <tr key={meal.id}>
                <td>{meal.id}</td>
                <td>{meal.detected_food}</td>
                <td>{meal.calories}</td>
                <td>{meal.protein}</td>
                <td>{meal.carbs}</td>
                <td>{meal.fat}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}