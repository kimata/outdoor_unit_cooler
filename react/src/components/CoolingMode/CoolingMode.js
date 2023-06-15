const CoolingMode = ({ isReady, ctrlStat }) => {
    const dutyInfo = (mode) => {
        return (
            <div className="container">
                <div className="row">
                    <div className="col-6">
                        <span className="me-1">On:</span>
                        <span className="display-6">{mode.duty.on_sec}</span>
                        <span className="ms-1">sec</span>
                    </div>
                    <div className="col-6">
                        <span className="me-1">Off:</span>
                        <span className="display-6">{Math.round(mode.duty.off_sec/60)}</span>
                        <span className="ms-1">min</span>
                    </div>
                </div>
            </div>
        )
    }
    
    const modeInfo = (mode) => {
        if (mode == null) {
            return loading()
        }
        
        return (
            <div>
                <div className="display-1 align-middle ms-1">
                    <span className="fw-bold">{mode.state}</span>
                </div>
                { dutyInfo(mode) }
            </div>
        )
    }
    const loading = () => {
        return (
            <span className="display-1 align-middle ms-4">
                <span className="display-5">Loading...</span>
            </span>
        )
    }
    
    return (
        <div className="container mt-4">
            <div className="card-deck mb-3 text-center">
                <div className="card mb-4 shadow-sm">
                    <div className="card-header">
                        <h4 className="my-0 font-weight-normal">現在の冷却モード</h4>
                    </div>
                    <div className="card-body">
                       { isReady ? modeInfo(ctrlStat.mode) : loading() }
                    </div>
                </div >      
            </div>
        </div>
  );
}

export default CoolingMode;
