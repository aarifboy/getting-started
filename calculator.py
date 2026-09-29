import math
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Calculator API")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class Calculation(BaseModel):
	left: float
	operator: str
	right: float


@app.get("/")
def home() -> FileResponse:
	return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/calc")
def calculate(calculation: Calculation) -> dict[str, float]:
	if not math.isfinite(calculation.left) or not math.isfinite(calculation.right):
		raise HTTPException(status_code=400, detail="Numbers must be finite.")

	operations = {
		"+": lambda: calculation.left + calculation.right,
		"-": lambda: calculation.left - calculation.right,
		"*": lambda: calculation.left * calculation.right,
		"/": lambda: calculation.left / calculation.right,
		"%": lambda: calculation.left % calculation.right,
	}
	if calculation.operator not in operations:
		raise HTTPException(status_code=400, detail="Unsupported operator.")
	if calculation.operator in {"/", "%"} and calculation.right == 0:
		raise HTTPException(status_code=400, detail="Cannot divide by zero.")

	result = operations[calculation.operator]()
	if not math.isfinite(result):
		raise HTTPException(status_code=400, detail="Result is outside the supported range.")
	return {"result": result}