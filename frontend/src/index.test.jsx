const { createRootMock, renderMock } = vi.hoisted(() => ({
  createRootMock: vi.fn(),
  renderMock: vi.fn(),
}));

vi.mock('react-dom/client', () => ({
  createRoot: createRootMock,
}));

vi.mock('./App', () => ({
  default: () => <div>AppRoot</div>,
}));

describe('index', () => {
  test('when the app boots, it mounts App into the root element', async () => {
    document.body.innerHTML = '<div id="root"></div>';

    createRootMock.mockReturnValue({ render: renderMock });

    await import('./index');

    expect(createRootMock).toHaveBeenCalledWith(document.getElementById('root'));
    expect(renderMock).toHaveBeenCalled();
  });
});
