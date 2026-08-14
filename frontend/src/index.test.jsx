import ReactDOM from 'react-dom/client';

jest.mock('./App', () => ({
  default: () => <div>AppRoot</div>,
}));

describe('index', () => {
  test('when the app boots, it mounts App into the root element', async () => {
    document.body.innerHTML = '<div id="root"></div>';

    const render = jest.fn();
    ReactDOM.createRoot = jest.fn(() => ({ render }));

    await import('./index');

    expect(ReactDOM.createRoot).toHaveBeenCalledWith(document.getElementById('root'));
    expect(render).toHaveBeenCalled();
  });
});
