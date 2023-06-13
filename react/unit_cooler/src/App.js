import './App.css';
import watering_icon from './img/watering.png'
import 'bootstrap/dist/css/bootstrap.min.css';

function App() {
    return (
<div className="App">
  <div class="d-flex flex-column flex-md-row align-items-center p-3 px-md-4 mb-3 bg-white border-bottom shadow-sm">
    <h5 class="display-6 my-0 mr-md-auto font-weight-normal">エアコン室外機冷却システム</h5>
  </div>

  <div class="container mt-4">
    <div class="card-deck mb-3 text-center">
      <div class="card mb-4 shadow-sm">
        <div class="card-header">
          <h4 class="my-0 font-weight-normal">本日の散水量</h4>
        </div>
            <div class="card-body">
           <img src={watering_icon} alt="🚰" width="120px" />
            <span class="display-1 align-middle ms-4"><span class="fw-bold">10.1</span> <span class="display-5">L</span></span>
        </div>
      </div >      
    </div>
  </div>
       
  <div class="container mt-4">
    <div class="card-deck mb-3 text-center">
      <div class="card mb-4 shadow-sm">
        <div class="card-header">
          <h4 class="my-0 font-weight-normal">センサー値</h4>
        </div>
        <div class="card-body">
          <table class="table">
            <thead>
              <tr>
                <th>#</th>
                <th>氏名</th>
                <th>得意言語</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>1</td>
                <td>エンジニア1</td>
                <td>PHP</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div >      
    </div>
  </div>
</div>

  );
}

export default App;
