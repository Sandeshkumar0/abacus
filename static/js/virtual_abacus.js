// Abacus State Management
class AbacusSimulator {
  constructor() {
    this.columns = 10;
    this.beadStates = [];
    this.initAbacus();
    this.setupEventListeners();
    this.render();
  }

  initAbacus() {
    this.beadStates = Array(this.columns)
      .fill(null)
      .map(() => ({
        topBeads: [false],
        bottomBeads: [false, false, false, false]
      }));
  }

  setupEventListeners() {
    document.getElementById('columns').addEventListener('change', (e) => {
      this.columns = Math.min(15, Math.max(1, parseInt(e.target.value) || 1));
      this.initAbacus();
      this.render();
    });
  }

  toggleTopBead(colIndex) {
    this.beadStates[colIndex].topBeads[0] =
      !this.beadStates[colIndex].topBeads[0];
    this.updateValue();
  }

  toggleBottomBead(colIndex, beadIndex) {
    const currentState = this.beadStates[colIndex].bottomBeads[beadIndex];
    if (!currentState) {
      for (let i = 0; i <= beadIndex; i++) {
        this.beadStates[colIndex].bottomBeads[i] = true;
      }
    } else {
      for (let i = beadIndex; i < 4; i++) {
        this.beadStates[colIndex].bottomBeads[i] = false;
      }
    }
    this.updateValue();
  }

  calculateValue() {
    let value = 0;
    this.beadStates.forEach((state, index) => {
      const position = this.beadStates.length - 1 - index;
      const topValue = state.topBeads[0] ? 5 : 0;
      const bottomValue = state.bottomBeads.filter((b) => b).length;
      const columnValue = topValue + bottomValue;
      value += columnValue * Math.pow(10, position);
    });
    return value;
  }

  updateValue() {
    document.getElementById('valueDisplay').textContent =
      this.calculateValue();
  }

  setRandomNumber() {
    const maxValue = Math.pow(10, this.columns) - 1;
    const randomValue = Math.floor(Math.random() * maxValue);
    const digits = randomValue
      .toString()
      .padStart(this.columns, '0')
      .split('')
      .map(Number);

    this.beadStates = digits.map((digit) => {
      const topBead = digit >= 5;
      const bottomCount = digit % 5;
      return {
        topBeads: [topBead],
        bottomBeads: [
          bottomCount >= 1,
          bottomCount >= 2,
          bottomCount >= 3,
          bottomCount >= 4
        ]
      };
    });
    this.render();
    this.updateValue();
  }

  reset() {
    this.initAbacus();
    this.render();
    this.updateValue();
  }

  render() {
    const abacusDisplay = document.getElementById('abacusDisplay');
    abacusDisplay.innerHTML = '';

    const grid = document.createElement('div');
    grid.className = 'abacus-grid';

    this.beadStates.forEach((state, colIndex) => {
      const rod = document.createElement('div');
      rod.className = 'rod';

      // Rod line
      const rodLine = document.createElement('div');
      rodLine.className = 'rod-line';
      rod.appendChild(rodLine);

      // Top beads
      const topBeadsDiv = document.createElement('div');
      topBeadsDiv.className = 'top-beads';

      state.topBeads.forEach((isActive) => {
        const bead = document.createElement('button');
        bead.className = `bead top-bead`;
        bead.style.transform = isActive ? 'translateY(60px)' : 'translateY(0)';
        bead.addEventListener('click', () => {
          this.toggleTopBead(colIndex);
          this.render();
        });
        topBeadsDiv.appendChild(bead);
      });

      rod.appendChild(topBeadsDiv);

      // Divider bar
      const divider = document.createElement('div');
      divider.className = 'divider-bar';
      rod.appendChild(divider);

      // Bottom beads
      const bottomBeadsDiv = document.createElement('div');
      bottomBeadsDiv.className = 'bottom-beads';

      state.bottomBeads.forEach((isActive, beadIndex) => {
        const bead = document.createElement('button');
        bead.className = 'bead';
        bead.style.transform =
          isActive ? 'translateY(-64px)' : 'translateY(0)';
        bead.addEventListener('click', () => {
          this.toggleBottomBead(colIndex, beadIndex);
          this.render();
        });
        bottomBeadsDiv.appendChild(bead);
      });

      rod.appendChild(bottomBeadsDiv);
      grid.appendChild(rod);
    });

    abacusDisplay.appendChild(grid);
  }
}

// Global simulator instance
let simulator = new AbacusSimulator();

// Global functions for buttons
function resetAbacus() {
  simulator.reset();
}

function setRandomNumber() {
  simulator.setRandomNumber();
}
